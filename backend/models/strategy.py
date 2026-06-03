from sqlalchemy import Column, Integer, String, Date, DateTime, DECIMAL, ForeignKey, Boolean, Text, JSON, UniqueConstraint
from sqlalchemy.sql import func
from models.database import Base

class Strategy(Base):
    __tablename__ = 'strategies'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False)  # short/mid/long
    description = Column(Text)
    parameters = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

class StrategyResult(Base):
    __tablename__ = 'strategy_results'
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey('strategies.id'))
    stock_code = Column(String(20), nullable=False)
    trade_date = Column(Date, nullable=False)
    signal_type = Column(String(20))  # buy/sell/hold
    buy_price = Column(DECIMAL(10, 4))
    stop_loss = Column(DECIMAL(10, 4))
    take_profit = Column(DECIMAL(10, 4))
    confidence_score = Column(DECIMAL(5, 4))
    reasoning = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint('strategy_id', 'stock_code', 'trade_date', name='uix_strategy_result'),
    )

class StrategyExecutionLog(Base):
    __tablename__ = 'strategy_execution_logs'
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey('strategies.id'))
    trade_date = Column(Date, nullable=False)
    status = Column(String(20), default='pending')  # pending/running/completed/failed
    stocks_count = Column(Integer, default=0)
    results_count = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
