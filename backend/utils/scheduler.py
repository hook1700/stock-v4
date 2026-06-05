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
        
        # 每日06:00 执行策略
        self.scheduler.add_job(
            self._execute_strategies_job,
            CronTrigger(hour=6, minute=0),
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
        """数据更新任务
        
        优化后的流程（适合每天23点运行）：
        1. 使用历史数据接口获取股票列表（更稳定）
        2. 获取行业分类信息并更新到股票表
        3. 增量更新当日日线数据
        """
        db = SessionLocal()
        try:
            logger.info('开始执行每日数据更新...')
            
            # 步骤1: 更新股票列表（使用历史数据接口，更适合非交易时段）
            # 每周一或首次运行时更新股票列表和行业信息
            from datetime import date as date_type
            today = date_type.today()
            should_update_stock_list = (today.weekday() == 0)  # 周一更新
            
            # 检查是否首次运行（数据库中没有股票数据）
            from models.stock import Stock
            stock_count = db.query(Stock).count()
            if stock_count == 0:
                should_update_stock_list = True
                logger.info('检测到首次运行，将更新股票列表')
            
            if should_update_stock_list:
                logger.info('开始更新股票列表和行业信息...')
                result = self.data_service.update_stock_list(db, use_history_api=True)
                if result['success']:
                    logger.info(f'股票列表更新完成，共 {result.get("count", 0)} 只')
                else:
                    logger.error(f'股票列表更新失败: {result.get("error", "未知错误")}')
            else:
                logger.info('今天不是周一，跳过股票列表更新（每周一更新）')
            
            # 步骤2: 增量更新日线数据（只更新今天的数据）
            logger.info('开始增量更新日线数据...')
            result = self.data_service.update_daily_data(db, use_incremental=True)
            
            if result['success']:
                logger.info(f'日线数据更新完成，共 {result.get("count", 0)} 条')
            else:
                logger.error(f'日线数据更新失败: {result.get("error", "未知错误")}')
                
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
