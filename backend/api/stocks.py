from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional, List
from datetime import date

from models.database import get_db
from models.stock import Stock, StockDaily
from data_sources.data_fetcher import DataFetcher

router = APIRouter(prefix='/stocks', tags=['股票'])

# 创建数据获取器实例
_fetcher = DataFetcher()

@router.get('/')
async def get_stocks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description='股票代码或名称搜索'),
    market: Optional[str] = Query(None, description='市场筛选'),
    industry: Optional[str] = Query(None, description='行业筛选'),
    sort_by: Optional[str] = Query('stock_code', description='排序字段'),
    sort_order: Optional[str] = Query('asc', description='排序方向: asc/desc'),
    db: Session = Depends(get_db)
):
    """获取股票列表"""
    query = db.query(Stock)
    
    if search:
        query = query.filter(
            (Stock.stock_code.like(f'%{search}%')) |
            (Stock.stock_name.like(f'%{search}%'))
        )
    
    if market:
        query = query.filter(Stock.market == market)
    
    if industry:
        query = query.filter(Stock.industry.like(f'%{industry}%'))
    
    total = query.count()
    
    # 排序
    if sort_order == 'desc':
        query = query.order_by(desc(getattr(Stock, sort_by, Stock.stock_code)))
    else:
        query = query.order_by(getattr(Stock, sort_by, Stock.stock_code))
    
    stocks = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        'total': total,
        'page': page,
        'page_size': page_size,
        'data': [
            {
                'id': s.id,
                'stock_code': s.stock_code,
                'stock_name': s.stock_name,
                'market': s.market,
                'industry': s.industry,
                'listing_date': s.listing_date.isoformat() if s.listing_date else None,
                'created_at': s.created_at.isoformat() if s.created_at else None
            }
            for s in stocks
        ]
    }

@router.get('/{stock_code}/daily')
async def get_stock_daily(
    stock_code: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """获取股票日线数据"""
    query = db.query(StockDaily).filter(StockDaily.stock_code == stock_code)
    
    if start_date:
        query = query.filter(StockDaily.trade_date >= start_date)
    if end_date:
        query = query.filter(StockDaily.trade_date <= end_date)
    
    daily_data = query.order_by(StockDaily.trade_date.desc()).limit(365).all()
    
    return {
        'stock_code': stock_code,
        'data': [
            {
                'trade_date': d.trade_date.isoformat(),
                'open_price': float(d.open_price) if d.open_price else None,
                'close_price': float(d.close_price) if d.close_price else None,
                'high_price': float(d.high_price) if d.high_price else None,
                'low_price': float(d.low_price) if d.low_price else None,
                'volume': int(d.volume) if d.volume else None,
                'turnover': float(d.turnover) if d.turnover else None,
                'pe_ratio': float(d.pe_ratio) if d.pe_ratio else None,
                'pb_ratio': float(d.pb_ratio) if d.pb_ratio else None
            }
            for d in daily_data
        ]
    }


@router.get('/industry/ths/summary')
async def get_ths_industry_summary():
    """获取同花顺行业板块概要数据
    
    返回同花顺行业板块的实时数据，包括：
    - 板块名称
    - 涨跌幅
    - 总成交量/成交额
    - 净流入
    - 上涨/下跌家数
    - 领涨股信息
    """
    try:
        df = _fetcher.get_ths_industry_summary()
        
        if df.empty:
            return {'success': False, 'error': '获取同花顺行业板块数据失败'}
        
        # 转换为字典列表
        result = []
        for _, row in df.iterrows():
            result.append({
                'serial': int(row.get('序号', 0)),
                'industry_name': str(row.get('板块', '')),
                'change_percent': float(row.get('涨跌幅', 0)) if row.get('涨跌幅') else 0.0,
                'total_volume': float(row.get('总成交量', 0)) if row.get('总成交量') else 0.0,
                'total_amount': float(row.get('总成交额', 0)) if row.get('总成交额') else 0.0,
                'net_inflow': float(row.get('净流入', 0)) if row.get('净流入') else 0.0,
                'up_count': int(row.get('上涨家数', 0)) if row.get('上涨家数') else 0,
                'down_count': int(row.get('下跌家数', 0)) if row.get('下跌家数') else 0,
                'avg_price': float(row.get('均价', 0)) if row.get('均价') else 0.0,
                'leading_stock': str(row.get('领涨股', '')),
                'leading_stock_price': float(row.get('领涨股-最新价', 0)) if row.get('领涨股-最新价') else 0.0,
                'leading_stock_change': float(row.get('领涨股-涨跌幅', 0)) if row.get('领涨股-涨跌幅') else 0.0
            })
        
        return {
            'success': True,
            'count': len(result),
            'data': result
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


@router.get('/industry/ths/list')
async def get_ths_industry_list():
    """获取同花顺行业板块名称列表
    
    返回同花顺行业板块的名称和代码列表
    """
    try:
        df = _fetcher.get_ths_industry_name_list()
        
        if df.empty:
            return {'success': False, 'error': '获取同花顺行业板块列表失败'}
        
        # 转换为字典列表
        result = []
        for _, row in df.iterrows():
            result.append({
                'name': str(row.get('name', '')),
                'code': str(row.get('code', ''))
            })
        
        return {
            'success': True,
            'count': len(result),
            'data': result
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
