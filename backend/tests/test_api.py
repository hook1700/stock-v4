import pytest
from datetime import date


def test_health_check(client):
    """测试健康检查接口"""
    response = client.get('/api/health')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ok'
    assert 'timestamp' in data


def test_get_stocks_empty(client):
    """测试获取空股票列表"""
    response = client.get('/api/stocks/')
    assert response.status_code == 200
    data = response.json()
    assert data['total'] == 0
    assert data['data'] == []


def test_get_stocks_with_data(client, sample_stocks):
    """测试获取股票列表"""
    response = client.get('/api/stocks/')
    assert response.status_code == 200
    data = response.json()
    assert data['total'] == 3
    assert len(data['data']) == 3


def test_get_stocks_search(client, sample_stocks):
    """测试股票搜索"""
    response = client.get('/api/stocks/?search=茅台')
    assert response.status_code == 200
    data = response.json()
    assert data['total'] == 1
    assert data['data'][0]['stock_name'] == '贵州茅台'


def test_get_strategies(client):
    """测试获取策略列表"""
    response = client.get('/api/strategies/')
    assert response.status_code == 200
    data = response.json()
    assert 'data' in data
    assert len(data['data']) == 9  # 9个策略


def test_get_strategy_results_empty(client):
    """测试获取空策略结果"""
    response = client.get('/api/strategies/results')
    assert response.status_code == 200
    data = response.json()
    assert data['total'] == 0
    assert data['data'] == []


def test_system_status(client):
    """测试系统状态接口"""
    response = client.get('/api/system/status')
    assert response.status_code == 200
    data = response.json()
    assert 'scheduler_running' in data
    assert 'version' in data


def test_daily_records_empty(client):
    """测试获取空每日记录"""
    response = client.get('/api/daily-records/')
    assert response.status_code == 200
    data = response.json()
    assert 'data' in data
