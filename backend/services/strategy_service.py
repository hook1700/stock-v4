import logging
from datetime import datetime, date
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models.database import get_db
from models.strategy import Strategy, StrategyResult, StrategyExecutionLog
from models.stock import Stock, StockDaily
from strategies.short_term import MABounceStrategy, BreakoutPullbackStrategy, StrongStockBounceStrategy
from strategies.mid_term import GrowthMAStrategy, ReversalStrategy, DividendStrategy
from strategies.long_term import BlueChipStrategy, DividendReinvestStrategy, PEGGrowthStrategy
from data_sources.data_fetcher import DataFetcher
import pandas as pd

logger = logging.getLogger(__name__)

class StrategyService:
    def __init__(self):
        self.strategies = [
            MABounceStrategy(),
            BreakoutPullbackStrategy(),
            StrongStockBounceStrategy(),
            GrowthMAStrategy(),
            ReversalStrategy(),
            DividendStrategy(),
            BlueChipStrategy(),
            DividendReinvestStrategy(),
            PEGGrowthStrategy()
        ]
        self.data_fetcher = DataFetcher()
    
    def get_all_strategies(self) -> List[Dict]:
        """获取所有策略信息"""
        return [
            {
                'id': i + 1,
                'name': s.name,
                'type': s.strategy_type,
                'description': s.description,
                'parameters': s.parameters
            }
            for i, s in enumerate(self.strategies)
        ]
    
    def run_strategy(self, strategy_index: int, db: Session, trade_date: date = None):
        """执行单个策略"""
        if trade_date is None:
            trade_date = date.today()
        
        try:
            strategy = self.strategies[strategy_index - 1]
            logger.info(f'开始执行策略: {strategy.name} ({strategy_index})')
            
            # 创建执行日志
            log = StrategyExecutionLog(
                strategy_id=strategy_index,
                trade_date=trade_date,
                status='running',
                started_at=datetime.now()
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            
            # 获取股票列表
            stocks = db.query(Stock).all()
            log.stocks_count = len(stocks)
            
            results = []
            
            for stock in stocks:
                try:
                    # 获取历史数据
                    daily_data = db.query(StockDaily).filter(
                        StockDaily.stock_code == stock.stock_code,
                        StockDaily.trade_date <= trade_date
                    ).order_by(StockDaily.trade_date).all()
                    
                    if len(daily_data) < 30:
                        continue
                    
                    df = pd.DataFrame([{
                        'date': d.trade_date,
                        'open': float(d.open_price) if d.open_price else 0,
                        'high': float(d.high_price) if d.high_price else 0,
                        'low': float(d.low_price) if d.low_price else 0,
                        'close': float(d.close_price) if d.close_price else 0,
                        'volume': int(d.volume) if d.volume else 0,
                        'turnover': float(d.turnover) if d.turnover else 0
                    } for d in daily_data])
                    
                    # 构造stock_info
                    stock_info = {
                        'turnover': float(daily_data[-1].turnover) if daily_data[-1].turnover else 0,
                        'pe': float(daily_data[-1].pe_ratio) if daily_data[-1].pe_ratio else None,
                        'pb': float(daily_data[-1].pb_ratio) if daily_data[-1].pb_ratio else None
                    }
                    
                    signal = strategy.analyze(stock.stock_code, df, stock.stock_name, stock_info)
                    
                    if signal and signal.signal_type == 'buy':
                        result = StrategyResult(
                            strategy_id=strategy_index,
                            stock_code=stock.stock_code,
                            trade_date=trade_date,
                            signal_type=signal.signal_type,
                            buy_price=signal.buy_price,
                            stop_loss=signal.stop_loss,
                            take_profit=signal.take_profit,
                            confidence_score=signal.confidence,
                            reasoning=signal.reasoning
                        )
                        db.add(result)
                        results.append(signal.to_dict())
                        
                except Exception as e:
                    logger.warning(f'处理{stock.stock_code}时出错: {e}')
                    continue
            
            db.commit()
            
            # 更新日志
            log.status = 'completed'
            log.results_count = len(results)
            log.completed_at = datetime.now()
            db.commit()
            
            logger.info(f'策略 {strategy.name} 执行完成，选出 {len(results)} 只股票')
            return {'success': True, 'results': results, 'count': len(results)}
            
        except Exception as e:
            logger.error(f'策略执行失败: {e}')
            if log:
                log.status = 'failed'
                log.error_message = str(e)
                log.completed_at = datetime.now()
                db.commit()
            return {'success': False, 'error': str(e)}
    
    def run_all_strategies(self, db: Session, trade_date: date = None):
        """执行所有策略"""
        if trade_date is None:
            trade_date = date.today()
        
        all_results = {}
        
        for i in range(1, 10):
            try:
                result = self.run_strategy(i, db, trade_date)
                all_results[self.strategies[i-1].name] = result
            except Exception as e:
                logger.error(f'策略 {i} 执行失败: {e}')
                all_results[self.strategies[i-1].name] = {'success': False, 'error': str(e)}
        
        return all_results
    
    def rerun_strategy(self, strategy_id: int, db: Session, trade_date: date = None):
        """重跑单个策略（先删除旧结果）"""
        if trade_date is None:
            trade_date = date.today()
        
        # 删除旧结果
        db.query(StrategyResult).filter(
            StrategyResult.strategy_id == strategy_id,
            StrategyResult.trade_date == trade_date
        ).delete()
        db.commit()
        
        return self.run_strategy(strategy_id, db, trade_date)
    
    def get_strategy_results(self, db: Session, strategy_id: int = None, 
                            trade_date: date = None, stock_code: str = None,
                            page: int = 1, page_size: int = 20):
        """获取策略结果"""
        query = db.query(StrategyResult)
        
        if strategy_id:
            query = query.filter(StrategyResult.strategy_id == strategy_id)
        if trade_date:
            query = query.filter(StrategyResult.trade_date == trade_date)
        if stock_code:
            query = query.filter(StrategyResult.stock_code == stock_code)
        
        total = query.count()
        results = query.order_by(desc(StrategyResult.created_at)).offset((page-1)*page_size).limit(page_size).all()
        
        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'data': [
                {
                    'id': r.id,
                    'strategy_id': r.strategy_id,
                    'strategy_name': self.strategies[r.strategy_id-1].name if r.strategy_id <= 9 else None,
                    'stock_code': r.stock_code,
                    'trade_date': r.trade_date.isoformat() if r.trade_date else None,
                    'signal_type': r.signal_type,
                    'buy_price': float(r.buy_price) if r.buy_price else None,
                    'stop_loss': float(r.stop_loss) if r.stop_loss else None,
                    'take_profit': float(r.take_profit) if r.take_profit else None,
                    'confidence_score': float(r.confidence_score) if r.confidence_score else None,
                    'reasoning': r.reasoning,
                    'created_at': r.created_at.isoformat() if r.created_at else None
                }
                for r in results
            ]
        }
