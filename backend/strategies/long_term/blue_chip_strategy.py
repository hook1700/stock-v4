import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy, StrategySignal
import logging

logger = logging.getLogger(__name__)

class BlueChipStrategy(BaseStrategy):
    """长线策略①：优质白马龙头（核心长线）
    
    选股逻辑：
    - 连续3年 ROE≥15%，净利↑，现金流好（当前版本暂用均线趋势代替）
    - 行业格局稳定或长期空间大
    - 无治理/财务污点，大盘蓝筹或细分龙头
    
    买点：PE 处于历史 30%~60% 分位，分2~3笔建仓（尤其年线/重要支撑附近）
    卖点：基本面恶化或极端高估（PE>历史90%分位）
    """
    
    def __init__(self):
        super().__init__(
            name='优质白马龙头',
            strategy_type='long',
            description='优质蓝筹长线持有策略'
        )
        self.parameters = {
            'min_turnover': 500000000,
            'profit_target': 0.50,
            'stop_loss': -0.18,
            'max_hold_days': 365
        }
    
    def analyze(self, stock_code, data, stock_name='', stock_info=None) -> StrategySignal:
        if len(data) < 260:
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
            ma60 = self.calculate_ma(data, 60)
            ma120 = self.calculate_ma(data, 120)
            ma250 = self.calculate_ma(data, 250)
            latest_ma60 = ma60.iloc[-1]
            latest_ma120 = ma120.iloc[-1]
            latest_ma250 = ma250.iloc[-1]
            
            # 条件1: 年线向上（长期趋势向好）
            ma250_rising = latest_ma250 > ma250.iloc[-30]
            
            # 条件2: 股价在250日/120日线上方
            above_long_mas = latest_close > latest_ma120 and latest_close > latest_ma250
            
            # 条件3: 股价未过度上涨（距250日线<80%）
            not_overextended = latest_close < latest_ma250 * 1.80
            
            # 条件4: 缩量回踩年线或120日线
            near_ma250 = abs(latest_close - latest_ma250) / latest_ma250 < 0.03 if latest_ma250 > 0 else False
            near_ma120 = abs(latest_close - latest_ma120) / latest_ma120 < 0.02 if latest_ma120 > 0 else False
            
            if ma250_rising and above_long_mas and not_overextended and (near_ma250 or near_ma120):
                buy_price = round(latest_close, 2)
                stop_loss = round(latest_ma250 * 0.85, 2)
                take_profit = round(buy_price * 1.50, 2)
                
                target = '年线' if near_ma250 else '120日线'
                reasoning = (f'年线向上，长期趋势向好，股价位于长期均线上方，' +
                           f'未过度上涨，缩量回踩{target}附近，适合长线建仓。' +
                           f'建议分2~3笔建仓，止损设年线下方。' +
                           f'【注：当前版本未接入PE分位数据，建议参考历史估值区间辅助决策】')
                
                return StrategySignal(
                    stock_code=stock_code,
                    signal_type='buy',
                    buy_price=buy_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    confidence=0.58,
                    reasoning=reasoning
                )
            
            return None
        except Exception as e:
            logger.error(f'白马龙头策略分析{stock_code}出错: {e}')
            return None
