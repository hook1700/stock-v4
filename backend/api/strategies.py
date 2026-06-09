from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date
from pydantic import BaseModel

from models.database import get_db
from services.strategy_service import StrategyService

# 添加请求模型
class ExecuteStrategyRequest(BaseModel):
    strategy_ids: Optional[List[int]] = None
    trade_date: Optional[date] = None

router = APIRouter(prefix='/strategies', tags=['策略'])
strategy_service = StrategyService()

@router.get('/')
async def get_strategies():
    """获取所有策略列表"""
    return {'data': strategy_service.get_all_strategies()}

@router.post('/execute')
async def execute_strategies(
    request: ExecuteStrategyRequest,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """执行策略"""
    strategy_ids = request.strategy_ids
    trade_date = request.trade_date
    
    if not strategy_ids:
        results = strategy_service.run_all_strategies(db, trade_date)
    else:
        results = {}
        for sid in strategy_ids:
            results[str(sid)] = strategy_service.run_strategy(sid, db, trade_date)
    
    return {
        'success': True,
        'results': results
    }

@router.get('/results')
async def get_strategy_results(
    strategy_id: Optional[int] = None,
    trade_date: Optional[date] = None,
    stock_code: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """获取策略执行结果"""
    return strategy_service.get_strategy_results(
        db, strategy_id=strategy_id, trade_date=trade_date,
        stock_code=stock_code, page=page, page_size=page_size
    )

@router.post('/{strategy_id}/rerun')
async def rerun_strategy(
    strategy_id: int,
    trade_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """重跑单个策略"""
    result = strategy_service.rerun_strategy(strategy_id, db, trade_date)
    return {
        'success': result.get('success', False),
        'message': '策略重跑完成',
        'result': result
    }