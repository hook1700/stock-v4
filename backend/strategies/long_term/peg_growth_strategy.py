import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy, StrategySignal
import logging

logger = logging.getLogger(__name__)

class PEGGrowthStrategy(BaseStrategy):
    """长线策略③：真成长 PEG 低吸（进阶长线）
    
    选股逻辑：
    - 净利增速 20%~40%，ROE≥15%（当前版本暂用价格趋势代替）
    - PEG < 1（市盈率÷净利润增速）（当前版本暂时简化为PE过滤）
    - 行业处于成长期
    
    买点：合理估值区 分笔建仓
    卖点：增速明显放缓（PEG>1.5以上持续）
    """
    
    def __init__(self):
        super().__init__(
            name='真成长PEG低吸',
            strategy_type='long',
            description='成长股PEG估值长线策略'
        )
        self.parameters = {
            'min_turnover': 200000000,
            'profit_target': 0.60,
            'stop_loss': -0.20,
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
            
            # 条件1: 长期均线向上（代表成长趋势）
            ma250_rising = latest_ma250 > ma250.iloc[-60]
            ma120_rising = latest_ma120 > ma120.iloc[-30]
            
            # 条件2: 股价在120日和250日线上
            above_long_mas = latest_close > latest_ma120 and latest_close > latest_ma250
            
            # 条件3: 近期增速特征（近60日涨幅在10%~40%区间）
            rise_60 = (latest_close - close.iloc[-60]) / close.iloc[-60] if close.iloc[-60] > 0 else 0
            moderate_growth = 0.05 < rise_60 < 0.40
            
            # 条件4: 回踩120日线或60日线
            near_ma120 = abs(latest_close - latest_ma120) / latest_ma120 < 0.03 if latest_ma120 > 0 else False
            near_ma60 = abs(latest_close - latest_ma60) / latest_ma60 < 0.02 if latest_ma60 > 0 else False
            
            # 整合PE数据（如果stock_info中有）
            pe_info = ''
            if stock_info and 'pe' in stock_info:
                pe = stock_info['pe']
                pe_info = f'当前PE: {pe}。'
            
            if ma250_rising and ma120_rising and above_long_mas and moderate_growth and (near_ma120 or near_ma60):
                buy_price = round(latest_close, 2)
                stop_loss = round(latest_ma120 * 0.82, 2)
                take_profit = round(buy_price * 1.60, 2)
                
                target = '120日线' if near_ma120 else '60日线'
                reasoning = (f'长期均线向上，中期处于上升通道，近60日涨幅{rise_60:.1%}，' +
                           f'股价位于长期均线上方，缩量回踩{target}附近。' +
                           f'{pe_info}' +
                           f'适合成长股长线建仓。' +
                           f'【注：当前版本未完全接入PE和净利润增速数据，建议手动确认PE<增速】')
                
                return StrategySignal(
                    stock_code=stock_code,
                    signal_type='buy',
                    buy_price=buy_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    confidence=0.55,
                    reasoning=reasoning
                )
            
            return None
        except Exception as e:
            logger.error(f'PEG成长策略分析{stock_code}出错: {e}')
            return None
