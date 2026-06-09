#!/usr/bin/env python3
"""
股票数据同步脚本 - 使用 Baostock 实现

功能：
1. 拉取A股股票列表并入库
2. 拉取过去一年交易数据并入库
3. 增量同步（只获取新增或更新的数据）

使用方法：
    # 首次运行：拉取股票列表 + 过去一年数据
    python sync_stock_data.py --init
    
    # 增量同步：只同步最新数据
    python sync_stock_data.py --incremental
    
    # 只更新股票列表
    python sync_stock_data.py --update-list
    
    # 只更新指定股票的历史数据
    python sync_stock_data.py --stock 000001 --history 365
"""

import argparse
import logging
import sys
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

# 条件导入数据库相关模块
HAS_DATABASE = False
Session = None
SessionLocal = None
engine = None
Base = None
Stock = None
StockDaily = None

try:
    from sqlalchemy.orm import Session
    from models.database import SessionLocal, engine, Base
    from models.stock import Stock, StockDaily
    HAS_DATABASE = True
    logger.info('数据库模块导入成功')
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.warning(f'数据库模块导入失败，将只支持文件输出模式: {e}')

# 导入 Baostock 客户端
try:
    import baostock as bs
    from data_sources.baostock_client import BaoStockClient
    HAS_BAOSTOCK = True
except ImportError:
    HAS_BAOSTOCK = False
    logger.warning('Baostock 未安装，请运行: pip install baostock')


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class StockDataSync:
    """股票数据同步类 - 使用 Baostock"""
    
    def __init__(self, db_session=None):
        """初始化
        
        Args:
            db_session: 数据库会话，如果为 None 则创建新会话
        """
        self.db = db_session
        self.bs_client = None
        self._login_bs()
    
    def _login_bs(self):
        """登录 Baostock"""
        if HAS_BAOSTOCK:
            try:
                self.bs_client = BaoStockClient()
                if self.bs_client.login():
                    logger.info('Baostock 登录成功')
                else:
                    logger.error('Baostock 登录失败')
                    self.bs_client = None
            except Exception as e:
                logger.error(f'Baostock 登录异常: {e}')
                self.bs_client = None
        else:
            logger.warning('Baostock 不可用')
    
    def _get_db_session(self):
        """获取数据库会话"""
        if self.db is not None:
            return self.db
        if HAS_DATABASE:
            return SessionLocal()
        return None
    
    def fetch_stock_list(self) -> pd.DataFrame:
        """拉取A股股票列表（不含交易数据）
        
        使用 Baostock 的 query_all_stock 接口获取A股列表
        
        Returns:
            DataFrame with columns: code, name
        """
        logger.info('=' * 60)
        logger.info('开始拉取A股股票列表...')
        logger.info('=' * 60)
        
        if not HAS_BAOSTOCK or not self.bs_client:
            logger.error('Baostock 不可用，无法获取股票列表')
            return pd.DataFrame()
        
        try:
            # 使用 BaoStockClient 获取股票列表
            df = self.bs_client.get_stock_list()
            
            if df.empty:
                logger.warning('Baostock 返回的股票列表为空，尝试使用备用方法')
                # 直接使用 baostock API
                df = self._fetch_stock_list_direct()
            else:
                logger.info(f'成功获取 {len(df)} 只股票')
            
            return df
            
        except Exception as e:
            logger.error(f'拉取股票列表失败: {e}')
            # 尝试直接使用 baostock API
            return self._fetch_stock_list_direct()
    
    def _fetch_stock_list_direct(self) -> pd.DataFrame:
        """直接使用 baostock API 获取股票列表"""
        try:
            # 使用固定的近期交易日日期
            trade_date = '2024-06-06'
            
            # 获取A股列表
            rs = bs.query_all_stock(day=trade_date)
            if rs.error_code != '0':
                logger.warning(f'使用日期 {trade_date} 获取失败，尝试使用今天日期')
                rs = bs.query_all_stock(day=datetime.now().strftime('%Y-%m-%d'))
                if rs.error_code != '0':
                    logger.error(f'获取股票列表失败: {rs.error_msg}')
                    return pd.DataFrame()
            
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                logger.warning('返回的股票列表为空')
                return pd.DataFrame()
            
            # 转换为 DataFrame
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            # 过滤只保留A股（code 以 sh.6 或 sz.0, sz.3 开头）
            if 'code' in df.columns:
                df = df[df['code'].str.match(r'^(sh\.6|sz\.[03])')]
            
            # 重命名列
            df = df.rename(columns={
                'code': 'code',
                'code_name': 'name'
            })
            
            # 确保 code 列为字符串且填充为6位（去掉 sh./sz. 前缀）
            df['code'] = df['code'].apply(
                lambda x: str(x).replace('sh.', '').replace('sz.', '').zfill(6)
            )
            
            logger.info(f'直接API调用获取股票列表成功，共 {len(df)} 只')
            return df
            
        except Exception as e:
            logger.error(f'直接API调用获取股票列表失败: {e}')
            return pd.DataFrame()
    
    def save_stock_list_to_db(self, df: pd.DataFrame) -> int:
        """将股票列表保存到数据库
        
        Args:
            df: 股票列表 DataFrame
            
        Returns:
            成功保存的股票数量
        """
        if not HAS_DATABASE:
            logger.error('数据库模块不可用，无法保存到数据库')
            return 0
        
        if df.empty:
            logger.warning('股票列表为空，无需保存')
            return 0
        
        db = self._get_db_session()
        if db is None:
            logger.error('无法获取数据库会话')
            return 0
        
        try:
            count = 0
            for _, row in df.iterrows():
                try:
                    code = str(row.get('code', '')).zfill(6)
                    name = str(row.get('name', ''))
                    
                    if not code or not name:
                        continue
                    
                    # 查询或创建
                    stock = db.query(Stock).filter(Stock.stock_code == code).first()
                    
                    if stock:
                        # 更新
                        stock.stock_name = name
                        stock.updated_at = datetime.now()
                    else:
                        # 创建
                        market = 'SH' if code.startswith('6') else 'SZ'
                        stock = Stock(
                            stock_code=code,
                            stock_name=name,
                            market=market
                        )
                        db.add(stock)
                    
                    count += 1
                    
                    # 每100条提交一次
                    if count % 100 == 0:
                        db.commit()
                        logger.info(f'已处理 {count}/{len(df)} 只股票...')
                        
                except Exception as e:
                    logger.warning(f'处理股票 {code} 出错: {e}')
                    continue
            
            db.commit()
            logger.info(f'股票列表保存完成，共 {count} 只')
            return count
            
        except Exception as e:
            logger.error(f'保存股票列表到数据库失败: {e}')
            db.rollback()
            return 0
        finally:
            if self.db is None:  # 如果是临时创建的会话，需要关闭
                db.close()
    
    def fetch_stock_history(self, stock_code: str, 
                           start_date: str = None, 
                           end_date: str = None) -> pd.DataFrame:
        """拉取单只股票的历史交易数据
        
        Args:
            stock_code: 股票代码（如 '000001'）
            start_date: 开始日期，格式 YYYY-MM-DD，默认为一年前
            end_date: 结束日期，格式 YYYY-MM-DD，默认为今天
            
        Returns:
            DataFrame with columns: date, code, open, high, low, close, volume, amount, turnover_rate
        """
        if not HAS_BAOSTOCK or not self.bs_client:
            logger.error(f'Baostock 不可用，无法获取 {stock_code} 历史数据')
            return pd.DataFrame()
        
        # 处理日期参数
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        
        try:
            # 使用 BaoStockClient 获取历史数据
            df = self.bs_client.get_stock_history(
                stock_code=stock_code,
                start_date=start_date,
                end_date=end_date
            )
            
            if df.empty:
                logger.debug(f'未获取到 {stock_code} 的历史数据')
            else:
                logger.debug(f'成功获取 {stock_code} 历史数据，共 {len(df)} 条记录')
            
            return df
            
        except Exception as e:
            logger.error(f'拉取 {stock_code} 历史数据失败: {e}')
            return pd.DataFrame()
    
    def save_stock_history_to_db(self, stock_code: str, df: pd.DataFrame) -> int:
        """将股票历史数据保存到数据库
        
        Args:
            stock_code: 股票代码
            df: 历史数据 DataFrame
            
        Returns:
            成功保存的记录数量
        """
        if not HAS_DATABASE:
            logger.error('数据库模块不可用，无法保存到数据库')
            return 0
        
        if df.empty:
            return 0
        
        db = self._get_db_session()
        if db is None:
            logger.error('无法获取数据库会话')
            return 0
        
        try:
            count = 0
            for _, row in df.iterrows():
                try:
                    # 解析日期
                    trade_date = row.get('date', '')
                    if isinstance(trade_date, str):
                        try:
                            trade_date = datetime.strptime(trade_date, '%Y-%m-%d').date()
                        except ValueError:
                            continue
                    
                    # 检查是否已存在
                    existing = db.query(StockDaily).filter(
                        StockDaily.stock_code == stock_code,
                        StockDaily.trade_date == trade_date
                    ).first()
                    
                    if existing:
                        # 已存在，跳过
                        continue
                    
                    # 解析价格
                    def parse_float(value):
                        if value is None or value == '' or value == '-':
                            return None
                        try:
                            return float(value)
                        except (ValueError, TypeError):
                            return None
                    
                    def parse_int(value):
                        if value is None or value == '' or value == '-':
                            return None
                        try:
                            return int(float(value))
                        except (ValueError, TypeError):
                            return None
                    
                    close_price = parse_float(row.get('close', 0))
                    if not close_price or close_price <= 0:
                        continue
                    
                    # 创建记录
                    daily = StockDaily(
                        stock_code=stock_code,
                        trade_date=trade_date,
                        open_price=parse_float(row.get('open', 0)),
                        close_price=close_price,
                        high_price=parse_float(row.get('high', 0)),
                        low_price=parse_float(row.get('low', 0)),
                        volume=parse_int(row.get('volume', 0)),
                        turnover=parse_float(row.get('amount', 0))
                    )
                    db.add(daily)
                    count += 1
                    
                except Exception as e:
                    logger.debug(f'处理 {stock_code} 的 {trade_date} 数据出错: {e}')
                    continue
            
            db.commit()
            return count
            
        except Exception as e:
            logger.error(f'保存 {stock_code} 历史数据到数据库失败: {e}')
            db.rollback()
            return 0
        finally:
            if self.db is None:  # 如果是临时创建的会话，需要关闭
                db.close()
    
    def init_sync(self, history_days: int = 365, limit: int = None) -> Tuple[int, int]:
        """初始化同步：拉取股票列表 + 过去一年交易数据
        
        Args:
            history_days: 获取最近多少天的历史数据，默认365天
            limit: 限制处理的股票数量（用于测试）
            
        Returns:
            (stock_count, history_count): 股票数量, 历史数据记录数
        """
        logger.info('=' * 60)
        logger.info('开始初始化同步...')
        logger.info('=' * 60)
        
        # 1. 拉取股票列表
        stock_df = self.fetch_stock_list()
        if stock_df.empty:
            logger.error('拉取股票列表失败')
            return 0, 0
        
        logger.info(f'拉取到 {len(stock_df)} 只股票')
        
        # 2. 保存股票列表到数据库
        stock_count = self.save_stock_list_to_db(stock_df)
        logger.info(f'股票列表已保存，共 {stock_count} 只')
        
        # 3. 拉取历史数据
        history_count = self.fetch_and_save_all_history(history_days, limit)
        
        logger.info('=' * 60)
        logger.info(f'初始化同步完成')
        logger.info(f'股票列表: {stock_count} 只')
        logger.info(f'历史数据: {history_count} 条')
        logger.info('=' * 60)
        
        return stock_count, history_count
    
    def fetch_and_save_all_history(self, days: int = 365, limit: int = None) -> int:
        """拉取并保存所有股票的历史数据
        
        Args:
            days: 获取最近多少天的历史数据
            limit: 限制处理的股票数量（用于测试）
            
        Returns:
            成功保存的记录总数
        """
        if not HAS_DATABASE:
            logger.error('数据库模块不可用，无法保存历史数据')
            return 0
        
        logger.info('=' * 60)
        logger.info(f'开始拉取历史数据（最近 {days} 天）...')
        logger.info('=' * 60)
        
        db = self._get_db_session()
        if db is None:
            logger.error('无法获取数据库会话')
            return 0
        
        try:
            # 获取所有股票
            stocks = db.query(Stock).all()
            
            if not stocks:
                logger.warning('数据库中还没有股票列表，请先运行初始化')
                return 0
            
            logger.info(f'数据库中共有 {len(stocks)} 只股票')
            
            # 如果有限制，只处理前 N 只
            if limit:
                stocks = stocks[:limit]
                logger.info(f'测试模式：只处理前 {limit} 只股票')
            
            # 计算日期范围
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            logger.info(f'日期范围: {start_date} ~ {end_date}')
            
            total_count = 0
            skip_count = 0
            
            for i, stock in enumerate(stocks):
                try:
                    code = stock.stock_code
                    
                    # 进度提示（每50只股票打印一次）
                    if (i + 1) % 50 == 0:
                        logger.info(f'进度: {i + 1}/{len(stocks)} ({(i + 1) / len(stocks) * 100:.1f}%)')
                    
                    # 获取历史数据
                    df = self.fetch_stock_history(
                        stock_code=code,
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    if df.empty:
                        skip_count += 1
                        continue
                    
                    # 保存到数据库
                    count = self.save_stock_history_to_db(code, df)
                    total_count += count
                    
                    # 每处理100只股票提交一次（在 save_stock_history_to_db 中已经提交）
                    if (i + 1) % 100 == 0:
                        logger.info(f'已处理 {i + 1} 只股票，共保存 {total_count} 条记录')
                        
                except Exception as e:
                    logger.warning(f'处理股票 {stock.stock_code} 出错: {e}')
                    continue
            
            logger.info('=' * 60)
            logger.info(f'历史数据拉取完成')
            logger.info(f'成功保存: {total_count} 条记录')
            logger.info(f'跳过（无数据）: {skip_count} 只股票')
            logger.info('=' * 60)
            
            return total_count
            
        except Exception as e:
            logger.error(f'拉取历史数据失败: {e}')
            return 0
        finally:
            if self.db is None:  # 如果是临时创建的会话，需要关闭
                db.close()
    
    def incremental_sync(self) -> int:
        """增量同步：只同步最新一天的数据
        
        Returns:
            成功保存的记录数量
        """
        logger.info('=' * 60)
        logger.info('开始增量同步...')
        logger.info('=' * 60)
        
        if not HAS_DATABASE:
            logger.error('数据库模块不可用，无法执行增量同步')
            return 0
        
        db = self._get_db_session()
        if db is None:
            logger.error('无法获取数据库会话')
            return 0
        
        try:
            # 获取所有股票
            stocks = db.query(Stock).all()
            
            if not stocks:
                logger.warning('数据库中还没有股票列表，请先运行初始化')
                return 0
            
            logger.info(f'数据库中共有 {len(stocks)} 只股票')
            
            # 获取昨天和今天的日期
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)
            
            # 尝试获取今天和昨天的数据
            target_dates = [today, yesterday]
            
            total_count = 0
            
            for target_date in target_dates:
                date_str = target_date.strftime('%Y-%m-%d')
                logger.info(f'尝试获取 {date_str} 的数据...')
                
                count = 0
                for i, stock in enumerate(stocks):
                    try:
                        code = stock.stock_code
                        
                        # 检查是否已存在该日期的数据
                        existing = db.query(StockDaily).filter(
                            StockDaily.stock_code == code,
                            StockDaily.trade_date == target_date
                        ).first()
                        
                        if existing:
                            # 已存在，跳过
                            continue
                        
                        # 获取该股票的历史数据（只获取 target_date 这一天）
                        df = self.fetch_stock_history(
                            stock_code=code,
                            start_date=date_str,
                            end_date=date_str
                        )
                        
                        if df.empty:
                            continue
                        
                        # 保存到数据库
                        saved = self.save_stock_history_to_db(code, df)
                        count += saved
                        
                        if (i + 1) % 100 == 0:
                            logger.info(f'日期 {date_str} - 进度: {i + 1}/{len(stocks)}')
                            
                    except Exception as e:
                        logger.debug(f'处理 {code} 出错: {e}')
                        continue
                
                if count > 0:
                    logger.info(f'日期 {date_str} 同步完成，共 {count} 条记录')
                    total_count += count
                    break  # 如果成功获取到数据，就不需要再获取前一天的了
                else:
                    logger.info(f'日期 {date_str} 无新数据')
            
            logger.info('=' * 60)
            logger.info(f'增量同步完成，共 {total_count} 条新记录')
            logger.info('=' * 60)
            
            return total_count
            
        except Exception as e:
            logger.error(f'增量同步失败: {e}')
            return 0
        finally:
            if self.db is None:  # 如果是临时创建的会话，需要关闭
                db.close()
    
    def update_stock_list_only(self) -> int:
        """只更新股票列表
        
        Returns:
            成功更新的股票数量
        """
        logger.info('=' * 60)
        logger.info('开始更新股票列表...')
        logger.info('=' * 60)
        
        # 拉取股票列表
        stock_df = self.fetch_stock_list()
        if stock_df.empty:
            logger.error('拉取股票列表失败')
            return 0
        
        logger.info(f'拉取到 {len(stock_df)} 只股票')
        
        # 保存股票列表到数据库
        stock_count = self.save_stock_list_to_db(stock_df)
        
        logger.info(f'股票列表更新完成，共 {stock_count} 只')
        return stock_count
    
    def cleanup(self):
        """清理资源"""
        if self.bs_client:
            try:
                self.bs_client.logout()
                logger.info('Baostock 已登出')
            except Exception as e:
                logger.warning(f'Baostock 登出失败: {e}')


def main():
    parser = argparse.ArgumentParser(description='股票数据同步脚本 - 使用 Baostock')
    parser.add_argument('--init', action='store_true', help='初始化同步：拉取股票列表 + 过去一年数据')
    parser.add_argument('--incremental', action='store_true', help='增量同步：只同步最新数据')
    parser.add_argument('--update-list', action='store_true', help='只更新股票列表')
    parser.add_argument('--stock', type=str, default=None, help='只处理指定股票代码（如 000001）')
    parser.add_argument('--history', type=int, default=365, help='获取最近多少天的历史数据（默认365天）')
    parser.add_argument('--limit', type=int, default=None, help='限制处理的股票数量（用于测试）')
    parser.add_argument('--output', type=str, default=None, help='将股票列表保存到指定文件（支持 .csv 或 .json）')
    
    args = parser.parse_args()
    
    # 如果没有指定任何选项，显示帮助
    if not any([args.init, args.incremental, args.update_list, args.stock]):
        parser.print_help()
        return
    
    # 检查 Baostock 是否可用
    if not HAS_BAOSTOCK:
        logger.error('Baostock 未安装，请运行: pip install baostock')
        return
    
    # 检查数据库是否可用（如果需要保存到数据库）
    if not HAS_DATABASE and not args.output:
        logger.error('数据库模块不可用，请使用 --output 来保存股票列表到文件')
        return
    
    sync = StockDataSync()
    
    try:
        if args.init:
            # 初始化同步
            sync.init_sync(history_days=args.history, limit=args.limit)
            
        elif args.incremental:
            # 增量同步
            sync.incremental_sync()
            
        elif args.update_list:
            # 只更新股票列表
            count = sync.update_stock_list_only()
            
            # 如果指定了输出文件，也保存到文件
            if args.output and count > 0:
                db = SessionLocal()
                stocks = db.query(Stock).all()
                stock_df = pd.DataFrame([
                    {'code': s.stock_code, 'name': s.stock_name}
                    for s in stocks
                ])
                sync._save_stock_list_to_file(stock_df, args.output)
                db.close()
            
        elif args.stock:
            # 处理指定股票
            code = args.stock.zfill(6)
            logger.info(f'处理股票 {code}...')
            
            # 获取历史数据
            df = sync.fetch_stock_history(code, 
                                         start_date=(datetime.now() - timedelta(days=args.history)).strftime('%Y-%m-%d'),
                                         end_date=datetime.now().strftime('%Y-%m-%d'))
            
            if not df.empty:
                logger.info(f'获取到 {len(df)} 条记录')
                
                # 保存到数据库
                count = sync.save_stock_history_to_db(code, df)
                logger.info(f'成功保存 {count} 条记录到数据库')
            else:
                logger.warning(f'未获取到 {code} 的历史数据')
        
    except KeyboardInterrupt:
        logger.info('用户中断，正在退出...')
    except Exception as e:
        logger.error(f'执行出错: {e}')
        raise
    finally:
        sync.cleanup()
        logger.info('完成')


if __name__ == '__main__':
    main()
