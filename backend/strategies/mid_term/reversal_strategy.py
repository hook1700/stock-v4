import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy, StrategySignal
import logging

logger = logging.getLogger(__name__)

class ReversalStrategy(BaseStrategy):
    """中线策略②：困境反转 / 业绩拐点（事件驱动中线）
    
    选股逻辑：
    - 前期调整 >30%，近期有企稳迹象
    - 底部放量站上60日线
    
    买点：第一根放量中大阳突破底部盘整 → 回踩不破阳线半分位/60日线买
    卖点：估值回归/利好兑现放巨量滞涨 → 止盈，重回底部或基本面证伪 → 止损-10%
    """
    
    def __init__(self):
        super().__init__(
            name='困境反转业绩拐点',
            strategy_type='mid',
            description='底部反转+业绩拐点中线策略（需后续补充财报数据）'
        )
        self.parameters = {
            'min_decline': 0.30,
            'min_turnover': 200000000,
            'profit_target': 0.25,
            'stop_loss': -0.10,
            'max_hold_days': 90
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
            high = data['high']
            low = data['low']
            volume = data['volume']
            latest_close = close.iloc[-1]
            
            # 计算均线
            ma60 = self.calculate_ma(data, 60)
            latest_ma60 = ma60.iloc[-1]
            
            # 条件1: 前期调整>30%
            high_60 = high.tail(60).max()
            if high_60 <= 0:
                return None
            decline = (high_60 - latest_close) / high_60
            if decline < self.parameters['min_decline']:
                return None
            
            # 条件2: 站上60日线
            above_ma60 = latest_close > latest_ma60
            
            # 条件3: 底部放量
            recent_vol = volume.tail(5).mean()
            prev_vol = volume.iloc[-15:-5].mean()
            volume_expanding = recent_vol > prev_vol * 1.3 if prev_vol > 0 else False
            
            # 条件4: 底部盘整形态（近30日振幅小）
            recent_30 = data.tail(30)
            range_30 = (recent_30['high'].max() - recent_30['low'].min()) / recent_30['low'].min() if recent_30['low'].min() > 0 else 1
            in_consolidation = range_30 < 0.15
            
            if above_ma60 and volume_expanding and in_consolidation:
                buy_price = round(latest_close, 2)
                # 止损设在阳线半分位或60日线
                stop_loss = round(max(buy_price * 0.90, latest_ma60 * 0.95), 2)
                take_profit = round(buy_price * (1 + self.parameters['profit_target']), 2)
                
                reasoning = (f'前期调整{decline:.1%}超30%，近30日底部盘整（振幅{range_30:.1%}），' +
                           f'近期放量站上60日线{latest_ma60:.2f}，困境反转信号，建议建仓。' +
                           f'【注：当前版本未接入财报数据，建议手动确认业绩拐点】')
                
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
            logger.error(f'困境反转策略分析{stock_code}出错: {e}')
            return None
