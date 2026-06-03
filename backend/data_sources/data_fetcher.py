import pandas as pd
import logging
from datetime import datetime, timedelta
from data_sources.baostock_client import BaoStockClient
from data_sources.akshare_client import AKShareClient

logger = logging.getLogger(__name__)

class DataFetcher:
    def __init__(self):
        self.bs_client = BaoStockClient()
        self.ak_client = AKShareClient()
    
    def get_stock_list(self):
        # 优先使用 AKShare，失败则用 BaoStock
        try:
            df = self.ak_client.get_a_stock_list()
            if not df.empty:
                return df
        except Exception as e:
            logger.warning(f'AKShare 获取股票列表失败，尝试 BaoStock: {e}')
        
        try:
            df = self.bs_client.get_stock_list()
            if not df.empty:
                return df
        except Exception as e:
            logger.error(f'BaoStock 获取股票列表也失败: {e}')
        
        return pd.DataFrame()
    
    def get_daily_data(self, stock_code, start_date, end_date=None):
        # 优先使用 AKShare
        try:
            df = self.ak_client.get_stock_history(stock_code, start_date=start_date, end_date=end_date)
            if not df.empty and len(df) > 0:
                return df
        except Exception as e:
            logger.warning(f'AKShare 获取{stock_code}历史数据失败，尝试 BaoStock: {e}')
        
        # BaoStock 需要加 market prefix
        try:
            formatted_code = self._format_stock_code(stock_code)
            df = self.bs_client.get_daily_data(formatted_code, start_date, end_date)
            if not df.empty and len(df) > 0:
                return df
        except Exception as e:
            logger.error(f'BaoStock 获取{stock_code}历史数据也失败: {e}')
        
        return pd.DataFrame()
    
    def _format_stock_code(self, code):
        # BaoStock 格式: sh.600000 / sz.000001
        if code.startswith('6'):
            return f'sh.{code}'
        else:
            return f'sz.{code}'
    
    def get_all_stocks_daily(self, trade_date=None):
        try:
            df = self.ak_client.get_a_stock_list()
            if not df.empty:
                return df
        except Exception as e:
            logger.error(f'获取全部股票行情失败: {e}')
        return pd.DataFrame()
    
    def cleanup(self):
        self.bs_client.logout()
