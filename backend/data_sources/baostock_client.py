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
        """获取股票列表（串行 + 限频）
        
        使用 query_all_stock 接口获取A股列表。
        为了避免非交易日返回空，使用一个固定的近期交易日日期。
        """
        self._wait_if_needed()
        try:
            if not self.is_logged_in:
                if not self.login():
                    return pd.DataFrame()
            
            # 使用固定的近期交易日日期（2024-06-06 是近期的一个交易日）
            # 这样可以避免今天是非交易日时返回空
            test_date = '2024-06-06'
            
            rs = bs.query_all_stock(day=test_date)
            if rs.error_code != '0':
                logger.error(f'获取股票列表失败: {rs.error_msg}')
                return pd.DataFrame()
            
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                logger.warning(f'使用日期 {test_date} 获取股票列表为空，尝试使用今天日期')
                rs = bs.query_all_stock(day=datetime.now().strftime('%Y-%m-%d'))
                if rs.error_code != '0':
                    logger.error(f'获取股票列表失败: {rs.error_msg}')
                    return pd.DataFrame()
                
                while (rs.error_code == '0') & rs.next():
                    data_list.append(rs.get_row_data())
            
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            # 过滤只保留A股（code 以 sh.6 或 sz.0, sz.3 开头）
            if 'code' in df.columns:
                df = df[df['code'].str.match(r'^(sh\.6|sz\.[03])')]
            
            logger.info(f'BaoStock 获取股票列表成功，共 {len(df)} 只')
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
    
    def get_stock_history(self, stock_code: str, 
                         start_date: str = None, 
                         end_date: str = None) -> pd.DataFrame:
        """获取股票历史数据（自动处理股票代码格式）
        
        此方法会自动将股票代码转换为 BaoStock 格式（sh.6xxxx / sz.xxxxx），
        并获取历史数据，最后将结果转换为统一格式。
        
        Args:
            stock_code: 股票代码（如 '000001' 或 '600000'）
            start_date: 开始日期，格式 YYYY-MM-DD，默认为一年前
            end_date: 结束日期，格式 YYYY-MM-DD，默认为今天
            
        Returns:
            DataFrame with columns: date, code, open, high, low, close, volume, amount, turnover_rate
        """
        # 处理日期参数
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        
        # 格式化股票代码（BaoStock 格式：sh.600000 / sz.000001）
        if stock_code.startswith('6'):
            formatted_code = f'sh.{stock_code}'
        else:
            formatted_code = f'sz.{stock_code}'
        
        # 获取历史数据
        df = self.get_daily_data(formatted_code, start_date, end_date)
        
        if df.empty:
            return df
        
        # 重命名列以匹配统一格式
        df = df.rename(columns={
            'date': 'date',
            'code': 'code',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume',
            'amount': 'amount',
            'turn': 'turnover_rate'
        })
        
        # 确保 code 列为字符串且填充为6位（去掉 sh./sz. 前缀）
        df['code'] = df['code'].apply(
            lambda x: str(x).replace('sh.', '').replace('sz.', '').zfill(6)
        )
        
        # 数值化处理（BaoStock 默认返回 str）
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'turnover_rate']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        logger.debug(f'获取 {stock_code} 历史数据成功，共 {len(df)} 条记录')
        return df
    
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