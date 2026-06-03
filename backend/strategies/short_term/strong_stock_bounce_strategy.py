import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy, StrategySignal
import logging

logger = logging.getLogger(__name__)

class StrongStockBounceStrategy(BaseStrategy):
    """短线策略③：强势股10日线反抽（顺势反弹）
    
    选股逻辑：
    - 近20日涨幅 > 大盘，有明显主力资金流入迹象
    - 回调至10日线或20日线出现承接（下影线、缩量）
    
    买点：第一次回踩10/20日线收阳 → 尾盘买，不做第二、第三次回踩（转弱）
    卖点：反弹至前高附近滞涨 → 卖出，破10日线或-7%止损
    ⚠️ 注意：熊市/下跌市不做此策略
    """
    
    def __init__(self):
        super().__init__(
            name='强势股10日线反抽',
            strategy_type='short',
            description='强势板块龙头回调均线反抽策略'
        )
        self.parameters = {
            'lookback': 20,
            'min_turnover': 500000000,
            'profit_target': 0.09,
            'stop_loss': -0.07,
            'max_hold_days': 7,
            'min_rise': 0.05  # 近20日涨幅至少5%
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
            
            lookback = self.parameters['lookback']
            recent_data = data.tail(lookback)
            
            # 条件1: 近20日涨幅 > 大盘（这里简化为正涨幅）
            rise_20 = (close.iloc[-1] - close.iloc[-lookback]) / close.iloc[-lookback] if close.iloc[-lookback] > 0 else 0
            if rise_20 < self.parameters['min_rise']:
                return None
            
            # 计算均线
            ma5 = self.calculate_ma(data, 5)
            ma10 = self.calculate_ma(data, 10)
            ma20 = self.calculate_ma(data, 20)
            latest_close = close.iloc[-1]
            latest_ma10 = ma10.iloc[-1]
            latest_ma20 = ma20.iloc[-1]
            
            # 条件2: 回调至10日或20日线
            near_ma10 = abs(latest_close - latest_ma10) / latest_ma10 < 0.015 if latest_ma10 > 0 else False
            near_ma20 = abs(latest_close - latest_ma20) / latest_ma20 < 0.015 if latest_ma20 > 0 else False
            
            if not (near_ma10 or near_ma20):
                return None
            
            # 条件3: 出现承接（下影线、缩量）
            latest_low = low.iloc[-1]
            latest_high = high.iloc[-1]
            body_size = abs(latest_close - data['open'].iloc[-1])
            lower_shadow = min(latest_close, data['open'].iloc[-1]) - latest_low
            
            # 有下影线且下影线至少是实体的0.5倍
            has_support = lower_shadow > body_size * 0.5 if body_size > 0 else lower_shadow > 0
            
            # 缩量
            volume = data['volume']
            vol_trend = self.get_volume_trend(data, 3, 10)
            volume_shrinking = vol_trend == 'shrinking' or volume.iloc[-1] < volume.iloc[-5:].mean()
            
            # 条件4: 第一次回踩收阳（非三连阴后第N次）
            # 简单检查：近3天内首日回踩
            prev_close = close.iloc[-2]
            prev_ma10 = ma10.iloc[-2]
            was_above_ma = prev_close > prev_ma10
            
            if was_above_ma and (near_ma10 or near_ma20) and has_support and volume_shrinking:
                buy_price = round(latest_close, 2)
                # 取前高作为止盈参考
                recent_high = high.tail(10).max()
                stop_loss = round(buy_price * (1 + self.parameters['stop_loss']), 2)
                
                # 止盈设为前高附近或8%
                take_profit = round(max(recent_high * 0.98, buy_price * 1.08), 2)
                
                target_ma = '10日线' if near_ma10 else '20日线'
                reasoning = f'近20日涨幅{rise_20:.1%}表现强势，首次回踩{target_ma}出现下影线承接，缩量企稳，建议顺势买入。'
                
                return StrategySignal(
                    stock_code=stock_code,
                    signal_type='buy',
                    buy_price=buy_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    confidence=0.72,
                    reasoning=reasoning
                )
            
            return None
        except Exception as e:
            logger.error(f'强势股反抽策略分析{stock_code}出错: {e}')
            return None
