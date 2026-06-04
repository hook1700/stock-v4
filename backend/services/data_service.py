import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from models.database import get_db
from models.stock import Stock, StockDaily
from models.data_update import DataUpdate
from data_sources.data_fetcher import DataFetcher
from config import settings

logger = logging.getLogger(__name__)

class DataService:
    def __init__(self):
        self.fetcher = DataFetcher()
    
    def update_stock_list(self, db: Session):
        """更新股票基础信息列表（包含申万二级行业）"""
        try:
            update_record = DataUpdate(
                update_type='stock_info',
                update_date=date.today(),
                status='running',
                started_at=datetime.now()
            )
            db.add(update_record)
            db.commit()
            db.refresh(update_record)
            
            # 先获取申万二级行业分类（建立股票代码 -> 行业名称的映射）
            logger.info('开始获取申万二级行业分类...')
            industry_mapping = {}
            try:
                industry_df = self.fetcher.ak_client.get_industry_classification(use_sw_second=True)
                if isinstance(industry_df, dict):
                    industry_mapping = industry_df
                    logger.info(f'申万二级行业分类获取成功，共 {len(industry_mapping)} 只股票')
                else:
                    logger.warning('申万二级行业分类返回格式异常，将跳过行业信息')
            except Exception as e:
                logger.warning(f'获取申万二级行业分类失败: {e}，将跳过行业信息')
            
            # 获取股票列表
            df = self.fetcher.get_stock_list()
            if df.empty:
                update_record.status = 'failed'
                update_record.error_message = '获取股票列表失败'
                update_record.completed_at = datetime.now()
                db.commit()
                return {'success': False, 'error': '获取股票列表失败'}
            
            count = 0
            for _, row in df.iterrows():
                try:
                    code = row.get('code') or row.get('stock_code', '')
                    if not code:
                        code = str(row.get('代码', ''))
                    name = row.get('name') or row.get('stock_name', '')
                    if not name:
                        name = str(row.get('名称', ''))
                    
                    if not code or not name:
                        continue
                    
                    # 查询或创建
                    stock = db.query(Stock).filter(Stock.stock_code == code).first()
                    
                    # 获取申万二级行业
                    industry_name = industry_mapping.get(code, '')
                    
                    if stock:
                        stock.stock_name = name
                        stock.updated_at = datetime.now()
                        # 更新行业信息（如果有）
                        if industry_name:
                            stock.industry = industry_name
                    else:
                        stock = Stock(
                            stock_code=code,
                            stock_name=name,
                            market='SZ' if code.startswith('0') or code.startswith('3') else 'SH',
                            industry=industry_name if industry_name else None
                        )
                        db.add(stock)
                    count += 1
                    
                    if count % 100 == 0:
                        db.commit()
                        
                except Exception as e:
                    logger.warning(f'处理股票信息出错: {e}')
                    continue
            
            db.commit()
            
            update_record.status = 'completed'
            update_record.records_updated = count
            update_record.completed_at = datetime.now()
            db.commit()
            
            logger.info(f'股票列表更新完成，共 {count} 只')
            return {'success': True, 'count': count}
            
        except Exception as e:
            logger.error(f'更新股票列表失败: {e}')
            if update_record:
                update_record.status = 'failed'
                update_record.error_message = str(e)
                update_record.completed_at = datetime.now()
                db.commit()
            return {'success': False, 'error': str(e)}
        finally:
            self.fetcher.cleanup()
    
    def update_daily_data(self, db: Session, target_date: date = None):
        """更新日线数据"""
        if target_date is None:
            target_date = date.today()
        
        try:
            update_record = DataUpdate(
                update_type='daily_data',
                update_date=target_date,
                status='running',
                started_at=datetime.now()
            )
            db.add(update_record)
            db.commit()
            db.refresh(update_record)
            
            # 获取A股行情
            df = self.fetcher.get_all_stocks_daily(target_date)
            if df.empty:
                update_record.status = 'failed'
                update_record.error_message = '获取行情数据失败'
                update_record.completed_at = datetime.now()
                db.commit()
                return {'success': False, 'error': '获取行情数据失败'}
            
            count = 0
            for _, row in df.iterrows():
                try:
                    code = str(row.get('代码', '')).replace('.', '')
                    if not code:
                        continue
                    
                    # 检查股票是否在列表中
                    stock = db.query(Stock).filter(Stock.stock_code == code).first()
                    if not stock:
                        continue
                    
                    # 解析价格
                    close_price = self._parse_price(row.get('最新价', 0))
                    open_price = self._parse_price(row.get('今开', 0))
                    high_price = self._parse_price(row.get('最高', 0))
                    low_price = self._parse_price(row.get('最低', 0))
                    volume = self._parse_volume(row.get('成交量', 0))
                    turnover = self._parse_price(row.get('成交额', 0))
                    pe = self._parse_price(row.get('市盈率', 0))
                    pb = self._parse_price(row.get('市净率', 0))
                    
                    # 检查是否已存在
                    existing = db.query(StockDaily).filter(
                        StockDaily.stock_code == code,
                        StockDaily.trade_date == target_date
                    ).first()
                    
                    if existing:
                        existing.open_price = open_price
                        existing.close_price = close_price
                        existing.high_price = high_price
                        existing.low_price = low_price
                        existing.volume = volume
                        existing.turnover = turnover
                        existing.pe_ratio = pe
                        existing.pb_ratio = pb
                    else:
                        daily = StockDaily(
                            stock_code=code,
                            trade_date=target_date,
                            open_price=open_price,
                            close_price=close_price,
                            high_price=high_price,
                            low_price=low_price,
                            volume=volume,
                            turnover=turnover,
                            pe_ratio=pe,
                            pb_ratio=pb
                        )
                        db.add(daily)
                    
                    count += 1
                    if count % 100 == 0:
                        db.commit()
                        
                except Exception as e:
                    logger.warning(f'处理{code}日线数据出错: {e}')
                    continue
            
            db.commit()
            
            update_record.status = 'completed'
            update_record.records_updated = count
            update_record.completed_at = datetime.now()
            db.commit()
            
            logger.info(f'日线数据更新完成，共 {count} 条')
            return {'success': True, 'count': count}
            
        except Exception as e:
            logger.error(f'更新日线数据失败: {e}')
            if update_record:
                update_record.status = 'failed'
                update_record.error_message = str(e)
                update_record.completed_at = datetime.now()
                db.commit()
            return {'success': False, 'error': str(e)}
        finally:
            self.fetcher.cleanup()
    
    def update_historical_data(self, db: Session, stock_code: str, days: int = 365):
        """更新单只股票历史数据"""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            df = self.fetcher.get_daily_data(
                stock_code,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
            
            if df.empty:
                return {'success': False, 'error': '获取历史数据失败'}
            
            count = 0
            for _, row in df.iterrows():
                try:
                    trade_date = row.get('date', '')
                    if isinstance(trade_date, str):
                        trade_date = datetime.strptime(trade_date, '%Y-%m-%d').date()
                    
                    close_price = self._parse_price(row.get('close', 0))
                    if close_price <= 0:
                        continue
                    
                    existing = db.query(StockDaily).filter(
                        StockDaily.stock_code == stock_code,
                        StockDaily.trade_date == trade_date
                    ).first()
                    
                    if not existing:
                        daily = StockDaily(
                            stock_code=stock_code,
                            trade_date=trade_date,
                            open_price=self._parse_price(row.get('open', 0)),
                            close_price=close_price,
                            high_price=self._parse_price(row.get('high', 0)),
                            low_price=self._parse_price(row.get('low', 0)),
                            volume=self._parse_volume(row.get('volume', 0)),
                            turnover=self._parse_price(row.get('amount', 0)),
                            pe_ratio=None,
                            pb_ratio=None
                        )
                        db.add(daily)
                        count += 1
                        
                except Exception as e:
                    continue
            
            db.commit()
            return {'success': True, 'count': count}
            
        except Exception as e:
            logger.error(f'更新{stock_code}历史数据失败: {e}')
            return {'success': False, 'error': str(e)}
        finally:
            self.fetcher.cleanup()
    
    def _parse_price(self, value):
        """解析价格"""
        if value is None or value == '' or value == '-':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _parse_volume(self, value):
        """解析成交量"""
        if value is None or value == '' or value == '-':
            return None
        try:
            v = float(value)
            return int(v)
        except (ValueError, TypeError):
            return None
