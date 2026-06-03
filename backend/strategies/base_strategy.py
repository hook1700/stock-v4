from abc import ABC, abstractmethod
from typing import Dict, List, Any
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

class StrategySignal:
    """策略信号"""
    def __init__(self, stock_code, signal_type, buy_price=None, stop_loss=None, 
                 take_profit=None, confidence=0.0, reasoning=''):
        self.stock_code = stock_code
        self.signal_type = signal_type  # buy/sell/hold
        self.buy_price = buy_price
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.confidence = confidence
        self.reasoning = reasoning
    
    def to_dict(self):
        return {
            'stock_code': self.stock_code,
            'signal_type': self.signal_type,
            'buy_price': self.buy_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'confidence': self.confidence,
            'reasoning': self.reasoning
        }

class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self, name, strategy_type, description=''):
        self.name = name
        self.strategy_type = strategy_type  # short/mid/long
        self.description = description
        self.parameters = {}
    
    def set_parameters(self, **params):
        self.parameters.update(params)
    
    def calculate_ma(self, data, period):
        """计算移动平均线"""
        return data['close'].rolling(window=period).mean()
    
    def calculate_volatility(self, data, period=20):
        """计算波动率"""
        return data['close'].rolling(window=period).std()
    
    def is_above_ma(self, data, period):
        """检查价格是否在均线上方"""
        ma = self.calculate_ma(data, period)
        return data['close'].iloc[-1] > ma.iloc[-1]
    
    def is_ma_rising(self, data, period):
        """检查均线是否向上"""
        ma = self.calculate_ma(data, period)
        return ma.iloc[-1] > ma.iloc[-5]
    
    def get_volume_trend(self, data, recent_days=5, compare_days=10):
        """获取成交量趋势: 放量/缩量"""
        recent_vol = data['volume'].tail(recent_days).mean()
        compare_vol = data['volume'].tail(compare_days).head(compare_days - recent_days).mean()
        if compare_vol == 0:
            return 'neutral'
        ratio = recent_vol / compare_vol
        if ratio > 1.3:
            return 'expanding'
        elif ratio < 0.7:
            return 'shrinking'
        return 'neutral'
    
    def calculate_rsi(self, data, period=14):
        """计算RSI指标"""
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @abstractmethod
    def analyze(self, stock_code, data) -> StrategySignal:
        """分析股票数据，返回策略信号"""
        pass
    
    def filter_by_turnover(self, stock_info, min_turnover=200000000):
        """按成交额过滤"""
        turnover = stock_info.get('turnover', stock_info.get('amount', 0))
        if isinstance(turnover, str):
            turnover = float(turnover) if turnover else 0
        return turnover >= min_turnover
    
    def is_st_stock(self, stock_name):
        """检查是否为ST股票"""
        if not stock_name:
            return False
        return 'ST' in stock_name.upper() or '*ST' in stock_name.upper()
