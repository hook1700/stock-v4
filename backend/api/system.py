from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date

from models.database import get_db
from models.data_update import DataUpdate
from models.strategy import StrategyExecutionLog
from services.data_service import DataService
from utils.scheduler import TaskScheduler

router = APIRouter(prefix='/system', tags=['系统'])

scheduler = TaskScheduler()
data_service = DataService()

@router.get('/status')
async def get_system_status(db: Session = Depends(get_db)):
    """获取系统状态"""
    # 获取最后数据更新
    last_update = db.query(DataUpdate).order_by(DataUpdate.created_at.desc()).first()
    
    # 获取最后策略执行
    last_strategy = db.query(StrategyExecutionLog).order_by(StrategyExecutionLog.created_at.desc()).first()
    
    # 获取统计
    total_updates = db.query(DataUpdate).filter(DataUpdate.status == 'completed').count()
    total_executions = db.query(StrategyExecutionLog).filter(StrategyExecutionLog.status == 'completed').count()
    
    return {
        'scheduler_running': scheduler.is_running(),
        'last_data_update': last_update.completed_at.isoformat() if last_update else None,
        'last_strategy_execution': last_strategy.completed_at.isoformat() if last_strategy else None,
        'total_data_updates': total_updates,
        'total_strategy_executions': total_executions,
        'version': '1.0.0'
    }

@router.post('/update-data')
async def trigger_data_update(db: Session = Depends(get_db)):
    """手动触发数据更新"""
    # 更新股票列表
    result1 = data_service.update_stock_list(db)
    # 更新日线数据
    result2 = data_service.update_daily_data(db)
    
    return {
        'success': result1.get('success', False) and result2.get('success', False),
        'stock_list': result1,
        'daily_data': result2
    }

@router.post('/scheduler/start')
async def start_scheduler():
    """启动定时任务"""
    scheduler.start()
    return {'success': True, 'message': '定时任务已启动', 'running': scheduler.is_running()}

@router.post('/scheduler/stop')
async def stop_scheduler():
    """停止定时任务"""
    scheduler.stop()
    return {'success': True, 'message': '定时任务已停止', 'running': scheduler.is_running()}
