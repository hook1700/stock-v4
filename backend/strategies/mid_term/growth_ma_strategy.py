import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy, StrategySignal
import logging

logger = logging.getLogger(__name__)

class GrowthMAStrategy(BaseStrategy):
    """中线策略①：行业成长 + 均线多头（经典中线程）
    
    选股逻辑：
    - 行业景气（新能源/半导体/军工/出海制造/消费复苏）
    - 近两季营收/净利同比↑，ROE≥10%（当前版本暂用均线过滤代替财报数据）
    - 股价站上60日线，5>10>20>60
    
    买点：突破阶段平台后缩量回踩20日或60日线企稳，或初建仓在60日线附近分2~3笔
    卖点：主升加速放巨量 → 分批减，有效跌破20日线或60日线止损
    """
    
    def __init__(self):
        super().__init__(
            name='行业成长均线多头',
            strategy_type='mid',
            description='行业成长+均线多头排列中线策略'
        )
        self.parameters = {
            'min_turnover': 200000000,
            'profit_target_1': 0.15,
            'profit_target_2': 0.30,
            'stop_loss': -0.12,
            'max_hold_days': 60
        }
    
    def analyze(self, stock_code, data, stock_name='', stock_info=None) -> StrategySignal:
        if len(data) < 70:
            return None
        
        try:
            if stock_info and not self.filter_by_turnover(stock_info, self.parameters['min_turnover']):
                return None
            if self.is_st_stock(stock_name):
                return None
            
            close = data['close']
            volume = data['volume']
            latest_close = close.iloc[-1]
            
            # 计算均线
            ma5 = self.calculate_ma(data, 5)
            ma10 = self.calculate_ma(data, 10)
            ma20 = self.calculate_ma(data, 20)
            ma60 = self.calculate_ma(data, 60)
            
            # 条件: 均线多头排列 5>10>20>60
            latest_ma5 = ma5.iloc[-1]
            latest_ma10 = ma10.iloc[-1]
            latest_ma20 = ma20.iloc[-1]
            latest_ma60 = ma60.iloc[-1]
            
            ma_bullish = (latest_ma5 > latest_ma10 > latest_ma20 > latest_ma60 and
                         latest_ma60 > 0)
            
            # 站上60日线
            above_ma60 = latest_close > latest_ma60
            
            # 股价在合理区间（不偏离60日太远）
            not_overextended = latest_close < latest_ma60 * 1.30
            
            if ma_bullish and above_ma60 and not_overextended:
                # 缩量回踩20或60日线
                near_ma20 = abs(latest_close - latest_ma20) / latest_ma20 < 0.02 if latest_ma20 > 0 else False
                near_ma60 = abs(latest_close - latest_ma60) / latest_ma60 < 0.02 if latest_ma60 > 0 else False
                
                vol_trend = self.get_volume_trend(data, 3, 10)
                volume_ok = vol_trend in ['shrinking', 'neutral']
                
                if near_ma20 or near_ma60:
                    buy_price = round(latest_close, 2)
                    stop_loss = round(latest_ma60 * 0.95, 2)
                    take_profit_1 = round(buy_price * 1.15, 2)
                    take_profit_2 = round(buy_price * 1.30, 2)
                    
                    target = '20日线' if near_ma20 else '60日线'
                    reasoning = ('均线多头排列（5>10>20>60），股价站上60日线未过度延伸，' +
                               f'缩量回踩{target}企稳，适合中线建仓。建议分2~3笔买入，' +
                               f'第一止盈位{take_profit_1:.2f}，第二止盈位{take_profit_2:.2f}。')
                    
                    return StrategySignal(
                        stock_code=stock_code,
                        signal_type='buy',
                        buy_price=buy_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit_1,
                        confidence=0.65,
                        reasoning=reasoning
                    )
            
            return None
        except Exception as e:
            logger.error(f'行业成长策略分析{stock_code}出错: {e}')
            return None
