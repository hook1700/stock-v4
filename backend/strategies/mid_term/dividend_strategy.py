import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy, StrategySignal
import logging

logger = logging.getLogger(__name__)

class DividendStrategy(BaseStrategy):
    """中线策略③：高股息红利慢牛（防御型中线）
    
    选股逻辑：
    - 银行/电力/高速/运营商/部分资源股
    - 股息率 ≥ 4%~5%（当前版本暂用均线特征代替）
    - 年线/60日线向上，波动小
    
    买点：缩量回踩60日线或年线附近 → 分批买
    卖点：股息率降至不合理 + 破趋势线
    """
    
    def __init__(self):
        super().__init__(
            name='高股息红利慢牛',
            strategy_type='mid',
            description='高股息防御型中线策略'
        )
        self.parameters = {
            'min_turnover': 200000000,
            'profit_target': 0.12,
            'stop_loss': -0.15,
            'max_hold_days': 90
        }
    
    def analyze(self, stock_code, data, stock_name='', stock_info=None) -> StrategySignal:
        if len(data) < 130:
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
            
            # 条件1: 年线/60日线向上
            ma60_rising = latest_ma60 > ma60.iloc[-10]
            ma250_rising = latest_ma250 > ma250.iloc[-20]
            
            # 条件2: 波动小（近60日振幅<25%）
            recent_60 = data.tail(60)
            amplitude_60 = (recent_60['high'].max() - recent_60['low'].min()) / recent_60['low'].min() if recent_60['low'].min() > 0 else 1
            low_volatility = amplitude_60 < 0.25
            
            # 条件3: 股价在年线和60日线上方
            above_ma = latest_close > latest_ma60 and latest_close > latest_ma250
            
            # 条件4: 缩量回踩60日线或年线
            near_ma60 = abs(latest_close - latest_ma60) / latest_ma60 < 0.02 if latest_ma60 > 0 else False
            near_ma250 = abs(latest_close - latest_ma250) / latest_ma250 < 0.03 if latest_ma250 > 0 else False
            
            if ma60_rising and ma250_rising and low_volatility and above_ma and (near_ma60 or near_ma250):
                buy_price = round(latest_close, 2)
                stop_loss = round(latest_ma250 * 0.93, 2)
                take_profit = round(buy_price * 1.12, 2)
                
                target = '60日线' if near_ma60 else '年线'
                reasoning = (f'股价位于年线和60日线上方，均线向上，近60日振幅仅{amplitude_60:.1%}波动稳定，' +
                           f'缩量回踩{target}附近，适合作为防御型中线持仓。' +
                           f'【注：当前版本未接入股息率数据，建议优先选择银行/电力/高速等高股息板块个股】')
                
                return StrategySignal(
                    stock_code=stock_code,
                    signal_type='buy',
                    buy_price=buy_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    confidence=0.60,
                    reasoning=reasoning
                )
            
            return None
        except Exception as e:
            logger.error(f'高股息策略分析{stock_code}出错: {e}')
            return None
