import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import json
from decimal import Decimal
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from starlette.responses import JSONResponse
from starlette.requests import Request

from models.database import engine, Base, SessionLocal
from models.strategy import Strategy as StrategyModel
from api import stocks, strategies, system, daily_record
from config import settings
from utils.scheduler import TaskScheduler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 访问日志过滤器：过滤 /api/health 请求
class HealthCheckFilter(logging.Filter):
    """过滤 /api/health 的访问日志"""
    def filter(self, record):
        # 如果日志记录中包含 /api/health，则过滤掉
        if hasattr(record, 'getMessage') and '/api/health' in record.getMessage():
            return False
        return True

# 将过滤器添加到 uvicorn.access 日志处理器
uvicorn_access = logging.getLogger('uvicorn.access')
uvicorn_access.addFilter(HealthCheckFilter())

# 创建数据库表（添加异常处理，避免因残留类型定义导致启动失败）
try:
    Base.metadata.create_all(bind=engine, checkfirst=True)
    logger.info('数据库表检查/创建完成')
except Exception as e:
    logger.warning(f'数据库表创建时出现警告（表可能已存在）: {e}')
    logger.info('将继续启动应用，假设数据库表已存在...')

# 全局调度器实例
scheduler = TaskScheduler()

# 自定义 JSON 编码器，处理 NaN、Infinity 等值
class SafeJSONEncoder(json.JSONEncoder):
    """安全的 JSON 编码器，处理 NaN、Infinity 等无法被 JSON 序列化的特殊值"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)
    
    def encode(self, obj):
        return json.dumps(obj, allow_nan=False, default=self.default)

    def iterencode(self, obj, _one_shot=False):
        # 将 NaN、Infinity 等转换为 None
        def convert_special_floats(o):
            if isinstance(o, float):
                if json.JSONEncoder().encode(o) == 'NaN' or o != o:  # NaN 检测
                    return None
                if o == float('inf'):
                    return None
                if o == float('-inf'):
                    return None
            elif isinstance(o, dict):
                return {k: convert_special_floats(v) for k, v in o.items()}
            elif isinstance(o, list):
                return [convert_special_floats(item) for item in o]
            return o
        
        converted = convert_special_floats(obj)
        return json.JSONEncoder().iterencode(converted, _one_shot)

def safe_json_dumps(obj, **kwargs):
    """安全的 json.dumps，将 NaN/Infinity 转换为 null"""
    def convert_nan_inf(o):
        if isinstance(o, float):
            if o != o:  # NaN 检测 (NaN != NaN)
                return None
            if o == float('inf') or o == float('-inf'):
                return None
        elif isinstance(o, dict):
            return {k: convert_nan_inf(v) for k, v in o.items()}
        elif isinstance(o, list):
            return [convert_nan_inf(item) for item in o]
        return o
    
    # 递归转换对象中的 NaN/Infinity
    converted = convert_nan_inf(obj)
    return json.dumps(converted, **kwargs)

class SafeJSONResponse(JSONResponse):
    """安全的 JSON 响应类，处理 NaN、Infinity 等特殊浮点值"""
    def render(self, content) -> bytes:
        return safe_json_dumps(content, ensure_ascii=False, default=str).encode('utf-8')

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info('应用启动...')
    
    # 初始化策略数据到数据库
    try:
        from services.strategy_service import StrategyService
        db = SessionLocal()
        strategy_service = StrategyService()
        
        # 获取所有策略信息
        all_strategies = strategy_service.get_all_strategies()
        
        for s in all_strategies:
            # 检查策略是否已存在
            existing = db.query(StrategyModel).filter(StrategyModel.id == s['id']).first()
            if not existing:
                # 创建新策略记录
                new_strategy = StrategyModel(
                    id=s['id'],
                    name=s['name'],
                    type=s['type'],
                    description=s['description'],
                    parameters=s['parameters'],
                    is_active=True
                )
                db.add(new_strategy)
                logger.info(f'添加策略到数据库: {s["name"]} (id={s["id"]})')
        
        db.commit()
        db.close()
        logger.info('策略数据初始化完成')
    except Exception as e:
        logger.warning(f'策略数据初始化失败（可能已存在）: {e}')
        if 'db' in locals():
            db.rollback()
            db.close()
    
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
    lifespan=lifespan,
    default_response_class=SafeJSONResponse  # 使用安全的 JSON 响应类
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