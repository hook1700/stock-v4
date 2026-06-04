import baostock as bs
import pandas as pd
from datetime import datetime, timedelta
import logging
import time
import threading

logger = logging.getLogger(__name__)

# 全局锁，确保 BaoStock 所有操作串行执行（同一时间只有一个请求）
_api_lock = threading.Lock()
# 上次请求时间（用于限频）
_last_request_time = 0
_min_interval = 0.5  # BaoStock 请求最小间隔(秒)


class BaoStockClient:
    """BaoStock 数据客户端，所有 API 调用均串行执行并限频"""
    
    def __init__(self):
        self.lg = None
        self.is_logged_in = False
    
    @classmethod
    def _wait_if_needed(cls):
        """限频等待：确保两次请求之间至少有 _min_interval 秒的间隔"""
        global _last_request_time, _api_lock
        while True:
            with _api_lock:
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
            logger.debug(f'BaoStock 限频等待: {sleep_time:.2f}秒')
            time.sleep(sleep_time)
    
    def login(self):
        """登录 BaoStock（串行 + 限频）"""
        self._wait_if_needed()
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
        """登出 BaoStock"""
        if self.is_logged_in:
            bs.logout()
            self.is_logged_in = False
    
    def get_stock_list(self):
        """获取股票列表（串行 + 限频）"""
        self._wait_if_needed()
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
        """获取日线数据（串行 + 限频）"""
        self._wait_if_needed()
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
        """获取行业分类（串行 + 限频）"""
        self._wait_if_needed()
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