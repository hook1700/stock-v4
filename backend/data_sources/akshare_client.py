import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import logging
import time

logger = logging.getLogger(__name__)

class AKShareClient:
    def __init__(self):
        self.last_request_time = 0
        self.min_interval = 0.2  # 最小请求间隔(秒)
    
    def _rate_limit(self):
        current = time.time()
        elapsed = current - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()
    
    def get_a_stock_list(self):
        try:
            self._rate_limit()
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
        try:
            self._rate_limit()
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
        try:
            self._rate_limit()
            df = ak.stock_industry_category_sw()
            return df
        except Exception as e:
            logger.error(f'获取申万行业分类失败: {e}')
            return pd.DataFrame()
    
    def get_stock_industry_sw(self, stock_code):
        try:
            self._rate_limit()
            df = ak.stock_individual_info_em(symbol=stock_code)
            return df
        except Exception as e:
            logger.error(f'获取{stock_code}行业信息失败: {e}')
            return pd.DataFrame()
