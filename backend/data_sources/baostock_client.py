import baostock as bs
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class BaoStockClient:
    def __init__(self):
        self.lg = None
        self.is_logged_in = False
    
    def login(self):
        try:
            self.lg = bs.login()
            if self.lg.error_code == '0':
                self.is_logged_in = True
                logger.info('BaoStock 登录成功')
                return True
            else:
                logger.error(f'BaoStock 登录失败: {self.lg.error_msg}')
                return False
        except Exception as e:
            logger.error(f'BaoStock 登录异常: {e}')
            return False
    
    def logout(self):
        if self.is_logged_in:
            bs.logout()
            self.is_logged_in = False
    
    def get_stock_list(self):
        try:
            if not self.is_logged_in:
                if not self.login():
                    return pd.DataFrame()
            
            rs = bs.query_all_stock(day=datetime.now().strftime('%Y-%m-%d'))
            if rs.error_code != '0':
                logger.error(f'获取股票列表失败: {rs.error_msg}')
                return pd.DataFrame()
            
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            df = pd.DataFrame(data_list, columns=rs.fields)
            return df
        except Exception as e:
            logger.error(f'获取股票列表异常: {e}')
            return pd.DataFrame()
    
    def get_daily_data(self, stock_code, start_date, end_date=None):
        try:
            if not self.is_logged_in:
                if not self.login():
                    return pd.DataFrame()
            
            if end_date is None:
                end_date = datetime.now().strftime('%Y-%m-%d')
            
            rs = bs.query_history_k_data_plus(
                stock_code,
                'date,code,open,high,low,close,volume,amount,turn,peTTM,pbMRQ',
                start_date=start_date,
                end_date=end_date,
                frequency='d',
                adjustflag='2'
            )
            
            if rs.error_code != '0':
                logger.error(f'获取{stock_code}日线数据失败: {rs.error_msg}')
                return pd.DataFrame()
            
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            df = pd.DataFrame(data_list, columns=rs.fields)
            return df
        except Exception as e:
            logger.error(f'获取{stock_code}日线数据异常: {e}')
            return pd.DataFrame()
    
    def get_stock_industry(self):
        try:
            if not self.is_logged_in:
                if not self.login():
                    return pd.DataFrame()
            
            rs = bs.query_stock_industry()
            if rs.error_code != '0':
                logger.error(f'获取行业分类失败: {rs.error_msg}')
                return pd.DataFrame()
            
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            df = pd.DataFrame(data_list, columns=rs.fields)
            return df
        except Exception as e:
            logger.error(f'获取行业分类异常: {e}')
            return pd.DataFrame()
