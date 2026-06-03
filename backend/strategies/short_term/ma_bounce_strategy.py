import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy, StrategySignal
import logging

logger = logging.getLogger(__name__)

class MABounceStrategy(BaseStrategy):
    """短线策略①：均线回踩低吸
    
    选股逻辑：
    - 股价在20日线上，20日线向上
    - 近5~10日温和放量上涨 → 缩量回踩5日或10日线
    - 板块有热度，日均成交≥3亿
    
    买点：回踩5/10日线 收小阳/十字星，尾盘14:50确认不破均线
    卖点：止盈+5%~10%，止损-7%，超10天未启动走人
    """
    
    def __init__(self):
        super().__init__(
            name='均线回踩低吸',
            strategy_type='short',
            description='趋势热点股缩量回踩均线低吸策略'
        )
        self.parameters = {
            'ma_period': 20,
            'support_ma': 5,
            'min_turnover': 300000000,  # 3亿
            'profit_target': 0.08,  # 8%
            'stop_loss': -0.07,  # -7%
            'max_hold_days': 10
        }
    
    def analyze(self, stock_code, data, stock_name='', stock_info=None) -> StrategySignal:
        if len(data) < 30:
            return None
        
        try:
            # 通用过滤
            if stock_info and not self.filter_by_turnover(stock_info, self.parameters['min_turnover']):
                return None
            if self.is_st_stock(stock_name):
                return None
            
            close = data['close']
            volume = data['volume']
            
            # 计算均线
            ma5 = self.calculate_ma(data, 5)
            ma10 = self.calculate_ma(data, 10)
            ma20 = self.calculate_ma(data, 20)
            
            latest_close = close.iloc[-1]
            latest_ma5 = ma5.iloc[-1]
            latest_ma10 = ma10.iloc[-1]
            latest_ma20 = ma20.iloc[-1]
            
            # 条件1: 股价在20日线上
            if latest_close < latest_ma20:
                return None
            
            # 条件2: 20日线向上
            if not self.is_ma_rising(data, 20):
                return None
            
            # 条件3: 近5~10日温和放量上涨
            vol_trend = self.get_volume_trend(data, 5, 10)
            recent_5_change = (close.iloc[-1] - close.iloc[-6]) / close.iloc[-6] if close.iloc[-6] > 0 else 0
            
            # 条件4: 缩量回踩5日或10日线
            is_near_ma5 = abs(latest_close - latest_ma5) / latest_ma5 < 0.02 if latest_ma5 > 0 else False
            is_near_ma10 = abs(latest_close - latest_ma10) / latest_ma10 < 0.02 if latest_ma10 > 0 else False
            
            volume_shrinking = vol_trend == 'shrinking'
            
            if (is_near_ma5 or is_near_ma10) and volume_shrinking:
                # 检查之前是否有一段上涨
                if recent_5_change > 0.03:  # 近5日涨幅>3%
                    buy_price = round(latest_close, 2)
                    stop_loss = round(buy_price * (1 + self.parameters['stop_loss']), 2)
                    take_profit = round(buy_price * (1 + self.parameters['profit_target']), 2)
                    
                    confidence = 0.7
                    if is_near_ma5:
                        confidence += 0.1
                    
                    reasoning = f'股价在20日线上且均线向上，近5日涨幅{recent_5_change:.2%}，缩量回踩{"5日线" if is_near_ma5 else "10日线"}，建议低吸买入。'
                    
                    return StrategySignal(
                        stock_code=stock_code,
                        signal_type='buy',
                        buy_price=buy_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        confidence=min(confidence, 1.0),
                        reasoning=reasoning
                    )
            
            return None
        except Exception as e:
            logger.error(f'均线回踩策略分析{stock_code}出错: {e}')
            return None
