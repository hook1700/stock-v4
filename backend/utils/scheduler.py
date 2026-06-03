import logging
from datetime import datetime, time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from services.data_service import DataService
from services.strategy_service import StrategyService
from models.database import SessionLocal

logger = logging.getLogger(__name__)

class TaskScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.data_service = DataService()
        self.strategy_service = StrategyService()
        self._running = False
    
    def start(self):
        """启动调度器"""
        if self._running:
            return
        
        # 每日23:00 更新数据
        self.scheduler.add_job(
            self._update_data_job,
            CronTrigger(hour=23, minute=0),
            id='daily_data_update',
            name='每日数据更新',
            replace_existing=True
        )
        
        # 每日00:00 执行策略
        self.scheduler.add_job(
            self._execute_strategies_job,
            CronTrigger(hour=0, minute=0),
            id='daily_strategy_execute',
            name='每日策略执行',
            replace_existing=True
        )
        
        self.scheduler.start()
        self._running = True
        logger.info('任务调度器已启动')
    
    def stop(self):
        """停止调度器"""
        if self._running:
            self.scheduler.shutdown()
            self._running = False
            logger.info('任务调度器已停止')
    
    def _update_data_job(self):
        """数据更新任务"""
        db = SessionLocal()
        try:
            logger.info('开始执行每日数据更新...')
            
            # 更新股票列表（每周一或首次运行）
            self.data_service.update_stock_list(db)
            
            # 更新日线数据
            result = self.data_service.update_daily_data(db)
            
            if result['success']:
                logger.info(f'数据更新完成，共 {result.get("count", 0)} 条')
            else:
                logger.error(f'数据更新失败: {result.get("error", "未知错误")}')
                
        except Exception as e:
            logger.error(f'数据更新任务异常: {e}')
        finally:
            db.close()
    
    def _execute_strategies_job(self):
        """策略执行任务"""
        db = SessionLocal()
        try:
            logger.info('开始执行策略分析...')
            results = self.strategy_service.run_all_strategies(db)
            
            success_count = sum(1 for r in results.values() if r.get('success'))
            total_count = len(results)
            logger.info(f'策略执行完成，{success_count}/{total_count} 个策略成功')
            
        except Exception as e:
            logger.error(f'策略执行任务异常: {e}')
        finally:
            db.close()
    
    def is_running(self):
        return self._running
