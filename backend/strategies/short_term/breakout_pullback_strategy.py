import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy, StrategySignal
import logging

logger = logging.getLogger(__name__)

class BreakoutPullbackStrategy(BaseStrategy):
    """短线策略②：突破缩量回踩（平台突破型）
    
    选股逻辑：
    - 近15~30日箱体震荡
    - 曾放量突破箱体/前高
    - 回踩原压力转支撑（平台下沿/10日线）缩量
    
    买点：回踩不破平台、收盘企稳，尾盘买
    卖点：再次上攻放量不涨停分批止盈，跌回平台内或-7%止损
    """
    
    def __init__(self):
        super().__init__(
            name='突破缩量回踩',
            strategy_type='short',
            description='横盘震荡后突破回踩确认策略'
        )
        self.parameters = {
            'box_period': 30,
            'min_turnover': 500000000,  # 5亿
            'profit_target': 0.10,  # 10%
            'stop_loss': -0.07,  # -7%
            'max_hold_days': 10
        }
    
    def analyze(self, stock_code, data, stock_name='', stock_info=None) -> StrategySignal:
        if len(data) < 40:
            return None
        
        try:
            if stock_info and not self.filter_by_turnover(stock_info, self.parameters['min_turnover']):
                return None
            if self.is_st_stock(stock_name):
                return None
            
            close = data['close']
            high = data['high']
            low = data['low']
            volume = data['volume']
            
            box_period = self.parameters['box_period']
            recent_data = data.tail(box_period)
            
            # 识别箱体上下沿
            box_high = recent_data['high'].max()
            box_low = recent_data['low'].min()
            box_range = box_high - box_low
            
            if box_range == 0 or box_low == 0:
                return None
            
            # 振幅不能太大（箱体特征）
            amplitude = box_range / box_low
            if amplitude > 0.25:  # 振幅超过25%不算箱体
                return None
            
            # 找突破点：近期有放量突破箱体上沿
            latest_close = close.iloc[-1]
            latest_vol = volume.iloc[-1]
            
            # 检查近10天内是否有放量突破
            breakout_found = False
            breakout_idx = -1
            recent_10 = data.tail(10)
            
            for i in range(len(recent_10) - 1, -1, -1):
                idx = len(data) - len(recent_10) + i
                if idx < box_period:
                    continue
                day_high = high.iloc[idx]
                day_vol = volume.iloc[idx]
                avg_vol = volume.iloc[idx-5:idx].mean()
                
                # 突破箱体上沿且放量
                if day_high > box_high * 0.98 and day_vol > avg_vol * 1.3:
                    breakout_found = True
                    breakout_idx = idx
                    break
            
            if not breakout_found:
                return None
            
            # 检查回踩：突破后价格回踩到平台下沿或10日线附近
            # 回踩必须在突破后
            if breakout_idx < 0 or len(data) - breakout_idx > 5:
                return None
            
            ma10 = self.calculate_ma(data, 10)
            latest_ma10 = ma10.iloc[-1]
            
            # 回踩条件：价格接近平台下沿或10日线，缩量
            near_support = (
                latest_close < box_high * 1.02 and  # 在突破点附近
                (latest_close > box_low * 0.98 or abs(latest_close - latest_ma10) / latest_ma10 < 0.02)
            )
            
            # 回踩缩量
            pullback_vol = volume.tail(len(data) - breakout_idx).mean()
            breakout_vol = volume.iloc[breakout_idx]
            volume_shrinking = pullback_vol < breakout_vol * 0.8
            
            if near_support and volume_shrinking:
                buy_price = round(latest_close, 2)
                stop_loss = round(min(buy_price * 0.93, box_low * 0.98), 2)
                take_profit = round(buy_price * 1.10, 2)
                
                reasoning = f'历经{box_period}日箱体震荡后放量突破，现缩量回踩支撑平台，突破确认买入点。箱体区间[{box_low:.2f}, {box_high:.2f}]，当前回踩企稳。'
                
                return StrategySignal(
                    stock_code=stock_code,
                    signal_type='buy',
                    buy_price=buy_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    confidence=0.75,
                    reasoning=reasoning
                )
            
            return None
        except Exception as e:
            logger.error(f'突破回踩策略分析{stock_code}出错: {e}')
            return None
