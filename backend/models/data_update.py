from sqlalchemy import Column, Integer, String, Date, DateTime, Text
from sqlalchemy.sql import func
from models.database import Base

class DataUpdate(Base):
    __tablename__ = 'data_updates'
    
    id = Column(Integer, primary_key=True, index=True)
    update_type = Column(String(50), nullable=False)
    update_date = Column(Date, nullable=False)
    status = Column(String(20), default='pending')
    records_updated = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
