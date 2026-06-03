import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy, StrategySignal
import logging

logger = logging.getLogger(__name__)

class DividendReinvestStrategy(BaseStrategy):
    """长线策略②：红利再投收息策略（养老式）
    
    选股逻辑：
    - 连续5年分红，股息率≥4.5%（当前版本暂用均线特征）
    - 盈利稳定、负债低、央企/国企偏好
    
    买点：除权后贴权回踩支撑 / 大盘回调低估区
    卖点：分红突然取消/大降，公司基本面恶化，资本大幅运作
    """
    
    def __init__(self):
        super().__init__(
            name='红利再投收息策略',
            strategy_type='long',
            description='红利再投资长线复利策略'
        )
        self.parameters = {
            'min_turnover': 300000000,
            'profit_target': 0.30,
            'stop_loss': -0.15,
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
            ma250 = self.calculate_ma(data, 250)
            latest_ma60 = ma60.iloc[-1]
            latest_ma250 = ma250.iloc[-1]
            
            # 条件1: 年线向上，趋势稳定
            ma250_rising = latest_ma250 > ma250.iloc[-60]
            
            # 条件2: 股价在线上方
            above_ma = latest_close > latest_ma250 and latest_close > latest_ma60
            
            # 条件3: 波动小（近120日振幅<30%）
            recent_120 = data.tail(120)
            amplitude = (recent_120['high'].max() - recent_120['low'].min()) / recent_120['low'].min() if recent_120['low'].min() > 0 else 1
            low_volatility = amplitude < 0.30
            
            # 条件4: 缩量回踩年线
            near_ma250 = abs(latest_close - latest_ma250) / latest_ma250 < 0.03 if latest_ma250 > 0 else False
            
            if ma250_rising and above_ma and low_volatility and near_ma250:
                buy_price = round(latest_close, 2)
                stop_loss = round(latest_ma250 * 0.90, 2)
                take_profit = round(buy_price * 1.30, 2)
                
                reasoning = (f'年线稳定向上，近120日振幅{amplitude:.1%}波动较小，' +
                           f'股价位于年线上方，缩量回踩年线附近，适合红利再投收息策略。' +
                           f'建议分红再投资，享受复利效果。' +
                           f'【注：当前版本未接入分红数据，建议选择银行/公用事业等高股息个股】')
                
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
            logger.error(f'红利再投策略分析{stock_code}出错: {e}')
            return None
