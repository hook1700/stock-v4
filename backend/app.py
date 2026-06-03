import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from models.database import engine, Base
from api import stocks, strategies, system, daily_record
from config import settings
from utils.scheduler import TaskScheduler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 全局调度器实例
scheduler = TaskScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info('应用启动...')
    # 启动定时任务调度器
    try:
        scheduler.start()
        logger.info('定时任务调度器已自动启动')
    except Exception as e:
        logger.warning(f'定时任务调度器启动失败（可能已运行）: {e}')
    yield
    # 关闭时停止调度器
    try:
        scheduler.stop()
        logger.info('定时任务调度器已停止')
    except Exception as e:
        logger.warning(f'定时任务调度器停止失败: {e}')
    logger.info('应用关闭...')

app = FastAPI(
    title='股票智能分析系统',
    description='基于多策略的股票筛选分析系统',
    version='1.0.0',
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# 注册路由
app.include_router(stocks.router, prefix='/api')
app.include_router(strategies.router, prefix='/api')
app.include_router(system.router, prefix='/api')
app.include_router(daily_record.router, prefix='/api')

@app.get('/')
async def root():
    return {
        'message': '股票智能分析系统 API',
        'version': '1.0.0',
        'docs': '/docs'
    }

@app.get('/api/health')
async def health_check():
    return {'status': 'ok', 'timestamp': __import__('datetime').datetime.now().isoformat()}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        'app:app',
        host='0.0.0.0',
        port=8000,
        reload=settings.DEBUG
    )