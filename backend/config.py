import os
from datetime import time
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 数据库配置
        DATABASE_URL: str = os.getenv('DATABASE_URL', 'postgresql://stock_user:stock_pass@localhost:5432/stock_analysis')
    
    # 数据源配置
    BAOSTOCK_USER: str = os.getenv('BAOSTOCK_USER', '')
    BAOSTOCK_PASSWORD: str = os.getenv('BAOSTOCK_PASSWORD', '')
    
    # 策略执行配置
    STRATEGY_EXECUTION_TIME: time = time(17, 45)  # 每日17:45执行
    DATA_UPDATE_TIME: time = time(17, 30)         # 数据更新时间
    
    # 股票筛选条件
    MIN_DAILY_TURNOVER: int = 200000000  # 2亿成交额
    MIN_SHORT_TURNOVER: int = 500000000  # 5亿成交额（短线）
    
    # 缓存配置
    REDIS_URL: str = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_TTL: int = 3600  # 1小时缓存
    
    # 应用配置
    DEBUG: bool = os.getenv('DEBUG', 'False').lower() == 'true'
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'stock-analysis-secret-key-2024')
    
    class Config:
        env_file = '.env'

settings = Settings()
