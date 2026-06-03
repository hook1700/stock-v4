from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, distinct
from typing import Optional, List
from datetime import date, timedelta

from models.database import get_db
from models.strategy import StrategyResult, StrategyExecutionLog, Strategy
from models.stock import Stock, StockDaily
from models.data_update import DataUpdate

router = APIRouter(prefix='/daily-records', tags=['每日记录'])

@router.get('/')
async def get_daily_records(
    record_date: Optional[date] = None,
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db)
):
    """获取每日记录摘要"""
    if record_date:
        start_date = record_date
        end_date = record_date
    else:
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)

    records = []

    for i in range((end_date - start_date).days + 1):
        current_date = start_date + timedelta(days=i)

        # 跳过周末
        if current_date.weekday() >= 5:
            continue

        # 数据更新状态
        data_update = db.query(DataUpdate).filter(
            DataUpdate.update_date == current_date,
            DataUpdate.status == 'completed'
        ).first()

        # 策略执行日志
        strategy_logs = db.query(StrategyExecutionLog).filter(
            StrategyExecutionLog.trade_date == current_date
        ).all()

        # 选股结果统计
        total_signals = db.query(func.count(StrategyResult.id)).filter(
            StrategyResult.trade_date == current_date
        ).scalar()

        # 各类策略结果数量
        short_signals = db.query(func.count(StrategyResult.id)).join(
            Strategy, StrategyResult.strategy_id == Strategy.id
        ).filter(
            StrategyResult.trade_date == current_date,
            Strategy.type == 'short'
        ).scalar()

        mid_signals = db.query(func.count(StrategyResult.id)).join(
            Strategy, StrategyResult.strategy_id == Strategy.id
        ).filter(
            StrategyResult.trade_date == current_date,
            Strategy.type == 'mid'
        ).scalar()

        long_signals = db.query(func.count(StrategyResult.id)).join(
            Strategy, StrategyResult.strategy_id == Strategy.id
        ).filter(
            StrategyResult.trade_date == current_date,
            Strategy.type == 'long'
        ).scalar()

        # 涉及的股票数量
        distinct_stocks = db.query(func.count(distinct(StrategyResult.stock_code))).filter(
            StrategyResult.trade_date == current_date
        ).scalar()

        records.append({
            'date': current_date.isoformat(),
            'day_of_week': ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][current_date.weekday()],
            'data_updated': data_update is not None,
            'data_update_count': data_update.records_updated if data_update else 0,
            'strategy_executed': len(strategy_logs) > 0,
            'strategy_count': len(strategy_logs),
            'completed_strategies': sum(1 for log in strategy_logs if log.status == 'completed'),
            'total_signals': total_signals or 0,
            'short_signals': short_signals or 0,
            'mid_signals': mid_signals or 0,
            'long_signals': long_signals or 0,
            'distinct_stocks': distinct_stocks or 0
        })

    return {'data': records}

@router.get('/{record_date}')
async def get_daily_record_detail(
    record_date: date,
    db: Session = Depends(get_db)
):
    """获取某一天的详细记录"""
    # 数据更新明细
    data_updates = db.query(DataUpdate).filter(
        DataUpdate.update_date == record_date
    ).all()

    # 策略执行明细
    strategy_logs = db.query(StrategyExecutionLog).filter(
        StrategyExecutionLog.trade_date == record_date
    ).all()

    # 选股结果明细
    results = db.query(StrategyResult).join(
        Strategy, StrategyResult.strategy_id == Strategy.id
    ).filter(
        StrategyResult.trade_date == record_date
    ).order_by(desc(StrategyResult.confidence_score)).all()

    # 市场情绪指标（基于涨跌幅统计）
    market_stats = db.query(
        func.count(StockDaily.id).label('total_stocks'),
        func.avg(StockDaily.close_price - StockDaily.open_price).label('avg_change'),
        func.sum(StockDaily.turnover).label('total_turnover')
    ).filter(
        StockDaily.trade_date == record_date
    ).first()

    return {
        'date': record_date.isoformat(),
        'data_updates': [
            {
                'id': d.id,
                'update_type': d.update_type,
                'status': d.status,
                'records_updated': d.records_updated,
                'started_at': d.started_at.isoformat() if d.started_at else None,
                'completed_at': d.completed_at.isoformat() if d.completed_at else None
            }
            for d in data_updates
        ],
        'strategy_logs': [
            {
                'id': log.id,
                'strategy_id': log.strategy_id,
                'status': log.status,
                'stocks_count': log.stocks_count,
                'results_count': log.results_count,
                'started_at': log.started_at.isoformat() if log.started_at else None,
                'completed_at': log.completed_at.isoformat() if log.completed_at else None
            }
            for log in strategy_logs
        ],
        'signals': [
            {
                'id': r.id,
                'stock_code': r.stock_code,
                'strategy_name': r.strategy.name if hasattr(r, 'strategy') else None,
                'signal_type': r.signal_type,
                'buy_price': float(r.buy_price) if r.buy_price else None,
                'stop_loss': float(r.stop_loss) if r.stop_loss else None,
                'take_profit': float(r.take_profit) if r.take_profit else None,
                'confidence_score': float(r.confidence_score) if r.confidence_score else None,
                'reasoning': r.reasoning
            }
            for r in results
        ],
        'market_stats': {
            'total_stocks': market_stats.total_stocks if market_stats else 0,
            'avg_change': float(market_stats.avg_change) if market_stats and market_stats.avg_change else None,
            'total_turnover': float(market_stats.total_turnover) if market_stats and market_stats.total_turnover else None
        }
    }
