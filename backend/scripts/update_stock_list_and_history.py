#!/usr/bin/env python3
"""
更新A股股票列表并获取历史数据

流程：
1. 使用 get_stock_info_a_code_name 获取A股股票列表（仅代码和名称，无交易信息）
2. 将股票列表入库（需要数据库）
3. 通过股票列表逐只获取历史数据

使用方法：
    # 只获取股票列表并保存到文件（不需要数据库）
    python update_stock_list_and_history.py --only-list --output stock_list.csv
    
    # 只更新股票列表到数据库
    python update_stock_list_and_history.py --only-list
    
    # 更新股票列表 + 获取历史数据（最近365天）
    python update_stock_list_and_history.py --with-history
    
    # 只获取历史数据（假设股票列表已入库）
    python update_stock_list_and_history.py --only-history --days 365
"""

import argparse
import logging
import sys
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    logger = logging.getLogger(__name__)
    logger.info('数据库模块导入成功')
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.warning(f'数据库模块导入失败，将只支持文件输出模式: {e}')

from data_sources.data_fetcher import DataFetcher

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def update_stock_list(db: Session, fetcher: DataFetcher) -> int:
    """更新股票列表
    
    Args:
        db: 数据库会话
        fetcher: 数据获取器
        
    Returns:
        成功更新的股票数量
    """
    logger.info('=' * 60)
    logger.info('开始更新股票列表...')
    logger.info('=' * 60)
    
    # 获取股票列表（仅代码和名称，无交易信息）
    df = fetcher.get_stock_info_a_code_name()
    
    if df.empty:
        logger.error('获取股票列表失败，请检查网络连接')
        return 0
    
    logger.info(f'获取到 {len(df)} 只股票')
    
    # 遍历股票列表，更新数据库
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
    logger.info(f'股票列表更新完成，共 {count} 只')
    return count


def update_history_data(db: Session, fetcher: DataFetcher, 
                        days: int = 365, limit: int = None) -> int:
    """更新历史数据
    
    Args:
        db: 数据库会话
        fetcher: 数据获取器
        days: 获取最近多少天的历史数据
        limit: 限制处理的股票数量（用于测试）
        
    Returns:
        成功更新的记录数量
    """
    logger.info('=' * 60)
    logger.info(f'开始更新历史数据（最近 {days} 天）...')
    logger.info('=' * 60)
    
    # 获取所有股票
    stocks = db.query(Stock).all()
    
    if not stocks:
        logger.warning('数据库中还没有股票列表，请先运行 --only-list')
        return 0
    
    logger.info(f'数据库中共有 {len(stocks)} 只股票')
    
    # 计算日期范围
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    logger.info(f'日期范围: {start_date} ~ {end_date}')
    
    # 如果有限制，只处理前 N 只
    if limit:
        stocks = stocks[:limit]
        logger.info(f'测试模式：只处理前 {limit} 只股票')
    
    count = 0
    skip_count = 0
    
    for i, stock in enumerate(stocks):
        try:
            code = stock.stock_code
            
            # 进度提示（每50只股票打印一次）
            if (i + 1) % 50 == 0:
                logger.info(f'进度: {i + 1}/{len(stocks)} ({((i + 1) / len(stocks) * 100):.1f}%)')
            
            # 获取历史数据
            df = fetcher.get_daily_data(
                stock_code=code,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
            
            if df.empty:
                skip_count += 1
                continue
            
            # 解析并入库
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
                        StockDaily.stock_code == code,
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
                        stock_code=code,
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
                    logger.debug(f'处理 {code} 的 {trade_date} 数据出错: {e}')
                    continue
            
            # 每处理100只股票提交一次
            if (i + 1) % 100 == 0:
                db.commit()
                logger.info(f'已提交 {i + 1} 只股票的数据')
                
        except Exception as e:
            logger.warning(f'处理股票 {stock.stock_code} 出错: {e}')
            continue
    
    db.commit()
    logger.info('=' * 60)
    logger.info(f'历史数据更新完成')
    logger.info(f'成功更新: {count} 条记录')
    logger.info(f'跳过（无数据）: {skip_count} 只股票')
    logger.info('=' * 60)
    return count


def save_stock_list_to_file(df: pd.DataFrame, output_path: str) -> bool:
    """将股票列表保存到文件
    
    Args:
        df: 股票列表 DataFrame
        output_path: 输出文件路径（支持 .csv 和 .json 扩展名）
        
    Returns:
        是否保存成功
    """
    try:
        ext = os.path.splitext(output_path)[1].lower()
        
        if ext == '.csv':
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            logger.info(f'股票列表已保存到 CSV 文件: {output_path}')
        elif ext == '.json':
            df.to_json(output_path, orient='records', force_ascii=False, indent=2)
            logger.info(f'股票列表已保存到 JSON 文件: {output_path}')
        else:
            # 默认保存为 CSV
            if not output_path.endswith('.csv'):
                output_path += '.csv'
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            logger.info(f'股票列表已保存到文件: {output_path}')
        
        return True
    except Exception as e:
        logger.error(f'保存文件失败: {e}')
        return False


def main():
    parser = argparse.ArgumentParser(description='更新A股股票列表并获取历史数据')
    parser.add_argument('--only-list', action='store_true', help='只获取股票列表')
    parser.add_argument('--only-history', action='store_true', help='只更新历史数据（需要数据库）')
    parser.add_argument('--with-history', action='store_true', help='获取股票列表 + 更新历史数据（需要数据库）')
    parser.add_argument('--days', type=int, default=365, help='获取最近多少天的历史数据（默认365天）')
    parser.add_argument('--limit', type=int, default=None, help='限制处理的股票数量（用于测试）')
    parser.add_argument('--output', type=str, default=None, help='将股票列表保存到指定文件（支持 .csv 或 .json）')
    
    args = parser.parse_args()
    
    # 如果没有指定任何选项，显示帮助
    if not any([args.only_list, args.only_history, args.with_history]):
        parser.print_help()
        return
    
    # 如果指定了 --output，强制获取股票列表（即使没有 --only-list）
    if args.output:
        args.only_list = True
    
    # 检查数据库模块是否可用
    if not HAS_DATABASE and (args.only_history or args.with_history):
        logger.error('数据库模块不可用，无法更新历史数据，请使用 --only-list --output 来保存股票列表')
        return
    
    fetcher = DataFetcher()
    db = None
    
    try:
        # 获取股票列表
        if args.only_list or args.with_history:
            logger.info('=' * 60)
            logger.info('开始获取股票列表...')
            logger.info('=' * 60)
            
            df = fetcher.get_stock_info_a_code_name()
            
            if df.empty:
                logger.error('获取股票列表失败，请检查网络连接')
                return
            
            logger.info(f'成功获取 {len(df)} 只股票')
            logger.info(f'前10只股票:\n{df.head(10).to_string()}')
            
            # 保存到文件
            if args.output:
                save_stock_list_to_file(df, args.output)
            
            # 更新到数据库
            if HAS_DATABASE and (not args.output or args.with_history):
                # 创建数据库表（如果不存在）
                Base.metadata.create_all(bind=engine)
                db = SessionLocal()
                update_stock_list(db, fetcher)
        
        # 更新历史数据
        if (args.only_history or args.with_history) and HAS_DATABASE:
            if db is None:
                # 创建数据库表（如果不存在）
                Base.metadata.create_all(bind=engine)
                db = SessionLocal()
            
            update_history_data(db, fetcher, days=args.days, limit=args.limit)
        
    except KeyboardInterrupt:
        logger.info('用户中断，正在退出...')
        if db:
            db.rollback()
    except Exception as e:
        logger.error(f'执行出错: {e}')
        if db:
            db.rollback()
        raise
    finally:
        if db:
            db.close()
        fetcher.cleanup()
        logger.info('完成')


if __name__ == '__main__':
    main()