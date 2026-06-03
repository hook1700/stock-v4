import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.database import Base, get_db
from app import app

# 使用内存 SQLite 进行测试
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    """创建测试数据库会话"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db):
    """创建测试客户端"""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
def sample_stocks(db):
    """创建测试股票数据"""
    from models.stock import Stock
    stocks = [
        Stock(stock_code='000001', stock_name='平安银行', market='SZ', industry='银行'),
        Stock(stock_code='600519', stock_name='贵州茅台', market='SH', industry='白酒'),
        Stock(stock_code='000858', stock_name='五粮液', market='SZ', industry='白酒'),
    ]
    for s in stocks:
        db.add(s)
    db.commit()
    return stocks
