import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import logging
import time
import threading

logger = logging.getLogger(__name__)

# 全局锁，确保 AKShare 所有操作串行执行（同一时间只有一个请求）
_api_lock = threading.Lock()
# 上次请求时间（用于限频）
_last_request_time = 0
_min_interval = 0.5  # AKShare 请求最小间隔(秒)，适当加大间隔避免限频


class AKShareClient:
    """AKShare 数据客户端，所有 API 调用均串行执行并限频"""
    
    def __init__(self):
        pass
    
    @classmethod
    def _wait_if_needed(cls):
        """限频等待：确保两次请求之间至少有 _min_interval 秒的间隔"""
        global _last_request_time
        while True:
            with cls._api_lock:
                # 再次检查，因为可能在我们等待锁的时候，其他线程已经更新了时间
                now = time.time()
                elapsed = now - _last_request_time
                if elapsed >= _min_interval:
                    # 足够间隔，更新时间并退出
                    _last_request_time = now
                    return
                else:
                    # 不够间隔，计算需要等待的时间
                    sleep_time = _min_interval - elapsed
            # 在锁外等待，避免阻塞其他线程
            logger.debug(f'AKShare 限频等待: {sleep_time:.2f}秒')
            time.sleep(sleep_time)
    
    def get_a_stock_list(self):
        """获取A股列表（串行 + 限频）"""
        self._wait_if_needed()
        try:
            df = ak.stock_zh_a_spot_em()
            # 重命名列以匹配我们的格式
            df = df.rename(columns={
                '代码': 'code',
                '名称': 'name',
                '最新价': 'latest_price',
                '涨跌幅': 'change_percent',
                '成交额': 'turnover',
                '市盈率-动态': 'pe',
                '市净率': 'pb'
            })
            return df
        except Exception as e:
            logger.error(f'获取A股列表失败: {e}')
            return pd.DataFrame()
    
    def get_stock_history(self, stock_code, period='daily', start_date=None, end_date=None):
        """获取股票历史数据（串行 + 限频）"""
        self._wait_if_needed()
        try:
            if start_date is None:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
            if end_date is None:
                end_date = datetime.now().strftime('%Y%m%d')
            
            # 转换日期格式
            start = start_date.replace('-', '') if '-' in start_date else start_date
            end = end_date.replace('-', '') if '-' in end_date else end_date
            
            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period=period,
                start_date=start,
                end_date=end,
                adjust='qfq'
            )
            
            # 重命名列
            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '涨跌幅': 'pct_change',
                '涨跌额': 'change',
                '换手率': 'turnover_rate'
            })
            return df
        except Exception as e:
            logger.error(f'获取{stock_code}历史数据失败: {e}')
            return pd.DataFrame()
    
    def get_industry_classification(self):
        """获取申万行业分类（串行 + 限频）"""
        self._wait_if_needed()
        try:
            df = ak.stock_industry_category_sw()
            return df
        except Exception as e:
            logger.error(f'获取申万行业分类失败: {e}')
            return pd.DataFrame()
    
    def get_stock_industry_sw(self, stock_code):
        """获取股票行业信息（串行 + 限频）"""
        self._wait_if_needed()
        try:
            df = ak.stock_individual_info_em(symbol=stock_code)
            return df
        except Exception as e:
            logger.error(f'获取{stock_code}行业信息失败: {e}')
            return pd.DataFrame()