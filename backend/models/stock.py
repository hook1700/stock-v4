from sqlalchemy import Column, Integer, String, Date, DateTime, DECIMAL, BigInteger, ForeignKey, UniqueConstraint, Text, JSON
from sqlalchemy.sql import func
from models.database import Base

class Stock(Base):
    __tablename__ = 'stocks'
    
    id = Column(Integer, primary_key=True, index=True)
    stock_code = Column(String(20), nullable=False, unique=True, index=True)
    stock_name = Column(String(100), nullable=False)
    market = Column(String(10))
    industry = Column(String(100))
    listing_date = Column(Date)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class StockDaily(Base):
    __tablename__ = 'stock_daily'
    
    id = Column(Integer, primary_key=True, index=True)
    stock_code = Column(String(20), nullable=False, index=True)
    trade_date = Column(Date, nullable=False)
    open_price = Column(DECIMAL(10, 4))
    close_price = Column(DECIMAL(10, 4))
    high_price = Column(DECIMAL(10, 4))
    low_price = Column(DECIMAL(10, 4))
    volume = Column(BigInteger)
    turnover = Column(DECIMAL(15, 2))
    pe_ratio = Column(DECIMAL(10, 4))
    pb_ratio = Column(DECIMAL(10, 4))
    created_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint('stock_code', 'trade_date', name='uix_stock_daily'),
    )
