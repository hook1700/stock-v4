import baostock as bs
import pandas as pd
from datetime import datetime, timedelta
import logging
import time
import random
import threading
from functools import wraps

logger = logging.getLogger(__name__)

# 请求超时设置（秒）
REQUEST_TIMEOUT = 30  # 单个请求超时时间

# 全局锁，确保所有操作串行执行（同一时间只有一个请求）
_api_lock = threading.Lock()
# 上次请求时间（用于限频）
_last_request_time = 0
# 随机延时范围（秒），模拟人工操作，避免被封
_MIN_DELAY = 0.5  # BaoStock 最小延时
_MAX_DELAY = 1.5  # BaoStock 最大延时

# 申万二级行业缓存（避免重复请求）
_sw_second_industry_cache = None
_sw_industry_map = {}  # 股票代码 -> 申万二级行业

# 重试配置
MAX_RETRIES = 3  # 最大重试次数
BASE_RETRY_DELAY = 5  # 基础重试延迟（秒），避免频繁请求被拉黑
MAX_RETRY_DELAY = 30  # 最大重试延迟（秒）


def retry_on_failure(max_retries=MAX_RETRIES, base_delay=BASE_RETRY_DELAY):
    """重试装饰器：在网络请求失败时自动重试
    
    使用指数退避策略，避免频繁重试导致IP被拉黑：
    - 第1次失败：等待 base_delay + 随机抖动
    - 第2次失败：等待 base_delay * 2 + 随机抖动
    - 第3次失败：等待 base_delay * 4 + 随机抖动
    
    Args:
        max_retries: 最大重试次数，默认3次
        base_delay: 基础重试延迟（秒），默认5秒
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # 检查是否是连接错误，如果是则使用更长的等待时间
                    error_msg = str(e).lower()
                    is_connection_error = any(
                        keyword in error_msg 
                        for keyword in ['connection', 'remote', 'timeout', 'aborted', 'refused']
                    )
                    
                    if attempt < max_retries - 1:
                        # 指数退避 + 随机抖动
                        if is_connection_error:
                            # 连接错误使用更长的等待时间
                            wait_time = min(base_delay * (2 ** attempt) + random.uniform(2, 5), MAX_RETRY_DELAY)
                        else:
                            # 其他错误使用标准指数退避
                            wait_time = min(base_delay * (attempt + 1) + random.uniform(1, 3), MAX_RETRY_DELAY)
                        
                        logger.warning(
                            f'{func.__name__} 第 {attempt + 1}/{max_retries} 次尝试失败: {e}，'
                            f'{wait_time:.1f}秒后重试...'
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(f'{func.__name__} 重试 {max_retries} 次后仍然失败: {e}')
            
            # 所有重试都失败，返回空结果（根据函数返回类型）
            # 通过检查函数名来判断返回类型
            func_name_lower = func.__name__.lower()
            if 'get' in func_name_lower:
                # 返回 DataFrame 的函数
                if any(keyword in func_name_lower for keyword in ['list', 'history', 'classification', 'stocks']):
                    return pd.DataFrame()
                # 返回 dict 的函数
                if 'industry' in func_name_lower and 'dict' in str(type).lower():
                    return {}
            # 其他情况抛出异常
            raise last_exception
        return wrapper
    return decorator


class AKShareClient:
    """股票数据客户端 - 使用 BaoStock 实现所有数据获取功能
    
    此类保持原有的方法签名和返回值格式，但内部实现全部使用 BaoStock。
    类名保留为 AKShareClient 以保持向后兼容性。
    """
    
    def __init__(self):
        self.login_status = False
    
    def _login(self):
        """登录 BaoStock"""
        if not self.login_status:
            lg = bs.login()
            if lg.error_code == '0':
                self.login_status = True
                logger.info('BaoStock 登录成功')
                return True
            else:
                logger.error(f'BaoStock 登录失败: {lg.error_msg}')
                return False
        return True
    
    def _logout(self):
        """登出 BaoStock"""
        if self.login_status:
            bs.logout()
            self.login_status = False
    
    @classmethod
    def _wait_if_needed(cls):
        """限频等待：使用随机延时，避免请求过于频繁"""
        global _last_request_time, _api_lock
        
        # 计算随机延时
        random_delay = random.uniform(_MIN_DELAY, _MAX_DELAY)
        
        with _api_lock:
            now = time.time()
            elapsed = now - _last_request_time
            
            if elapsed < random_delay:
                # 不够间隔，需要等待
                sleep_time = random_delay - elapsed
            else:
                # 已经足够间隔
                sleep_time = 0
            
            # 更新上次请求时间为当前时间 + 将要睡眠的时间
            _last_request_time = now + sleep_time
        
        # 在锁外等待，避免阻塞其他线程
        if sleep_time > 0:
            logger.debug(f'BaoStock 限频等待: {sleep_time:.2f}秒 (随机范围: {_MIN_DELAY}-{_MAX_DELAY}秒)')
            time.sleep(sleep_time)
    
    def _random_sleep(self, min_sleep=0.5, max_sleep=1.5):
        """请求完成后随机睡眠，降低被限流风险
        
        Args:
            min_sleep: 最小睡眠秒数，默认0.5秒
            max_sleep: 最大睡眠秒数，默认1.5秒
        """
        sleep_time = random.uniform(min_sleep, max_sleep)
        logger.debug(f'请求完成后随机睡眠 {sleep_time:.2f} 秒')
        time.sleep(sleep_time)
    
    @retry_on_failure(max_retries=3)
    def get_a_stock_list(self):
        """获取A股列表（使用 BaoStock）
        
        注意：此方法使用 query_all_stock 接口获取A股列表。
        
        Returns:
            DataFrame with columns: code, name, ...
        """
        self._wait_if_needed()
        try:
            # 登录
            if not self._login():
                raise Exception('BaoStock 登录失败')
            
            # 使用固定的近期交易日日期
            trade_date = '2024-06-06'
            
            # 获取A股列表
            rs = bs.query_all_stock(day=trade_date)
            if rs.error_code != '0':
                logger.warning(f'使用日期 {trade_date} 获取失败，尝试使用今天日期')
                rs = bs.query_all_stock(day=datetime.now().strftime('%Y-%m-%d'))
                if rs.error_code != '0':
                    raise Exception(rs.error_msg)
            
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                logger.warning('BaoStock 返回的股票列表为空')
                return pd.DataFrame()
            
            # 转换为 DataFrame
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            # 过滤只保留A股（code 以 sh.6 或 sz.0, sz.3 开头）
            if 'code' in df.columns:
                df = df[df['code'].str.match(r'^(sh\.6|sz\.[03])')]
            
            # 重命名列以匹配我们的格式
            df = df.rename(columns={
                'code': 'code',
                'code_name': 'name'
            })
            
            # 确保 code 列为字符串且填充为6位（去掉 sh./sz. 前缀）
            df['code'] = df['code'].apply(
                lambda x: str(x).replace('sh.', '').replace('sz.', '').zfill(6)
            )
            
            # 请求完成后随机睡眠
            self._random_sleep(min_sleep=1.0, max_sleep=2.0)
            
            logger.info(f'获取A股列表成功，共 {len(df)} 只')
            return df
        except Exception as e:
            logger.error(f'获取A股列表失败: {e}')
            raise  # 让重试装饰器处理
        finally:
            self._logout()
    
    @retry_on_failure(max_retries=3, base_delay=10)
    def get_stock_info_a_code_name(self):
        """获取全A股（沪深京）股票代码和名称（仅股票信息，无交易信息）
        
        使用 BaoStock 的 query_all_stock 接口获取股票代码和名称。
        
        Returns:
            DataFrame with columns: code（str，如 '000001'）、name（str，如 '平安银行'）
        """
        self._wait_if_needed()
        try:
            # 登录
            if not self._login():
                raise Exception('BaoStock 登录失败')
            
            logger.info('开始通过 BaoStock 获取A股股票列表...')
            
            # 使用固定的近期交易日日期
            trade_date = '2024-06-06'
            
            # 获取A股列表
            rs = bs.query_all_stock(day=trade_date)
            if rs.error_code != '0':
                logger.warning(f'使用日期 {trade_date} 获取失败，尝试使用今天日期')
                rs = bs.query_all_stock(day=datetime.now().strftime('%Y-%m-%d'))
                if rs.error_code != '0':
                    raise Exception(rs.error_msg)
            
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                logger.warning('BaoStock 返回的股票列表为空')
                return pd.DataFrame()
            
            # 转换为 DataFrame
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            # 过滤只保留A股
            if 'code' in df.columns:
                df = df[df['code'].str.match(r'^(sh\.6|sz\.[03])')]
            
            # 重命名列以匹配我们的格式
            df = df.rename(columns={
                'code': 'code',
                'code_name': 'name'
            })
            
            # 确保 code 列为字符串且填充为6位（去掉 sh./sz. 前缀）
            df['code'] = df['code'].apply(
                lambda x: str(x).replace('sh.', '').replace('sz.', '').zfill(6)
            )
            
            logger.info(f'获取A股股票列表成功，共 {len(df)} 只')
            self._random_sleep(min_sleep=1.0, max_sleep=2.0)
            return df
            
        except Exception as e:
            logger.error(f'获取A股股票列表失败: {e}')
            raise  # 让重试装饰器处理
        finally:
            self._logout()
    
    @retry_on_failure(max_retries=3, base_delay=10)
    def get_stock_list_from_history(self, trade_date=None):
        """通过历史数据接口获取A股列表（推荐非交易时段使用）
        
        此方法通过 query_all_stock 接口获取股票列表。
        
        Args:
            trade_date: 交易日期，格式 YYYYMMDD 或 YYYY-MM-DD，默认为昨天
            
        Returns:
            DataFrame with columns: code, name, ... (包含基本股票信息)
        """
        self._wait_if_needed()
        try:
            # 登录
            if not self._login():
                raise Exception('BaoStock 登录失败')
            
            logger.info('开始通过 BaoStock 获取股票列表...')
            
            # 确定交易日期
            if trade_date is None:
                target_date = datetime.now().strftime('%Y-%m-%d')
            else:
                # 统一日期格式为 YYYY-MM-DD
                target_date = trade_date.replace('-', '') if '-' in str(trade_date) else str(trade_date)
                if len(target_date) == 8:
                    target_date = f'{target_date[:4]}-{target_date[4:6]}-{target_date[6:8]}'
            
            # 获取A股列表
            rs = bs.query_all_stock(day=target_date)
            if rs.error_code != '0':
                logger.warning(f'使用日期 {target_date} 获取失败，尝试使用 fixed 日期')
                # 使用固定的近期交易日日期
                rs = bs.query_all_stock(day='2024-06-06')
                if rs.error_code != '0':
                    raise Exception(rs.error_msg)
            
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                logger.warning('BaoStock 返回的股票列表为空')
                return pd.DataFrame()
            
            # 转换为 DataFrame
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            # 过滤只保留A股
            if 'code' in df.columns:
                df = df[df['code'].str.match(r'^(sh\.6|sz\.[03])')]
            
            # 重命名列以匹配我们的格式
            df = df.rename(columns={
                'code': 'code',
                'code_name': 'name'
            })
            
            # 确保 code 列为字符串且填充为6位（去掉 sh./sz. 前缀）
            df['code'] = df['code'].apply(
                lambda x: str(x).replace('sh.', '').replace('sz.', '').zfill(6)
            )
            
            logger.info(f'获取股票列表成功，共 {len(df)} 只')
            self._random_sleep(min_sleep=1.0, max_sleep=2.0)
            return df
            
        except Exception as e:
            logger.error(f'获取股票列表失败: {e}')
            raise  # 让重试装饰器处理
        finally:
            self._logout()
    
    @retry_on_failure(max_retries=3)
    def get_stock_history(self, stock_code, period='daily', start_date=None, end_date=None):
        """获取股票历史数据（使用 BaoStock）
        
        Args:
            stock_code: 股票代码（如 '000001'）
            period: 周期，'daily' 为日线
            start_date: 开始日期，格式 YYYYMMDD 或 YYYY-MM-DD
            end_date: 结束日期，格式 YYYYMMDD 或 YYYY-MM-DD
            
        Returns:
            DataFrame with columns: date, code, open, high, low, close, volume, amount, ...
        """
        self._wait_if_needed()
        try:
            # 登录
            if not self._login():
                raise Exception('BaoStock 登录失败')
            
            # 处理日期参数
            if start_date is None:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            if end_date is None:
                end_date = datetime.now().strftime('%Y-%m-%d')
            
            # 统一日期格式为 YYYY-MM-DD
            if '-' not in str(start_date):
                start_date = f'{str(start_date)[:4]}-{str(start_date)[4:6]}-{str(start_date)[6:8]}'
            if '-' not in str(end_date):
                end_date = f'{str(end_date)[:4]}-{str(end_date)[4:6]}-{str(end_date)[6:8]}'
            
            # 格式化股票代码（BaoStock 格式：sh.600000 / sz.000001）
            if stock_code.startswith('6'):
                formatted_code = f'sh.{stock_code}'
            else:
                formatted_code = f'sz.{stock_code}'
            
            # 获取历史数据
            rs = bs.query_history_k_data_plus(
                formatted_code,
                'date,code,open,high,low,close,volume,amount,turn',
                start_date=start_date,
                end_date=end_date,
                frequency='d',
                adjustflag='2'  # 2: 前复权
            )
            
            if rs.error_code != '0':
                raise Exception(rs.error_msg)
            
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                logger.warning(f'未获取到 {stock_code} 的历史数据')
                return pd.DataFrame()
            
            # 转换为 DataFrame
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            # 重命名列以匹配我们的格式
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
            
            # 请求完成后随机睡眠
            self._random_sleep(min_sleep=1.0, max_sleep=2.0)
            
            logger.info(f'获取 {stock_code} 历史数据成功，共 {len(df)} 条记录')
            return df
        except Exception as e:
            logger.error(f'获取{stock_code}历史数据失败: {e}')
            raise  # 让重试装饰器处理
        finally:
            self._logout()
    
    @retry_on_failure(max_retries=3)
    def get_sw_second_industry(self):
        """获取行业分类基本信息（使用 BaoStock）
        
        Returns:
            DataFrame with columns: code, name, industry, ...
        """
        self._wait_if_needed()
        try:
            # 登录
            if not self._login():
                raise Exception('BaoStock 登录失败')
            
            logger.info('开始通过 BaoStock 获取行业分类信息...')
            
            # 获取行业分类
            rs = bs.query_stock_industry()
            if rs.error_code != '0':
                raise Exception(rs.error_msg)
            
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                logger.warning('BaoStock 返回的行业分类为空')
                return pd.DataFrame()
            
            # 转换为 DataFrame
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            logger.info(f'获取行业分类信息成功，共 {len(df)} 条记录')
            # 请求完成后随机睡眠
            self._random_sleep(min_sleep=1.0, max_sleep=2.0)
            return df
        except Exception as e:
            logger.error(f'获取行业分类信息失败: {e}')
            raise  # 让重试装饰器处理
        finally:
            self._logout()
    
    def get_sw_second_industry_stocks(self, index_code=None):
        """获取行业成分股
        
        Args:
            index_code: 行业指数代码（当前版本忽略此参数）
            
        Returns:
            DataFrame with columns: index_code, stock_code, stock_name, etc.
        """
        logger.warning('get_sw_second_industry_stocks: 建议使用 get_industry_classification')
        return pd.DataFrame()
    
    @retry_on_failure(max_retries=3)
    def get_industry_classification(self, use_sw_second=True):
        """获取行业分类（使用 BaoStock）
        
        使用 BaoStock 的 query_stock_industry 接口获取股票行业分类。
        
        Args:
            use_sw_second: 是否使用行业分类，默认为True
            
        Returns:
            返回 dict: {stock_code: industry_name}
        """
        global _sw_industry_map
        
        if use_sw_second:
            # 如果缓存中有数据，直接返回
            if _sw_industry_map:
                logger.info(f'从缓存获取行业分类，共 {len(_sw_industry_map)} 只股票')
                return _sw_industry_map.copy()
            
            try:
                self._wait_if_needed()
                
                # 登录
                if not self._login():
                    raise Exception('BaoStock 登录失败')
                
                logger.info('开始获取行业分类数据...')
                
                # 获取行业分类
                rs = bs.query_stock_industry()
                if rs.error_code != '0':
                    raise Exception(rs.error_msg)
                
                data_list = []
                while (rs.error_code == '0') & rs.next():
                    data_list.append(rs.get_row_data())
                
                if not data_list:
                    logger.warning('行业分类数据为空')
                    return {}
                
                # 转换为 DataFrame
                industry_df = pd.DataFrame(data_list, columns=rs.fields)
                
                # 构建股票代码到行业的映射
                for _, row in industry_df.iterrows():
                    stock_code = str(row.get('code', '')).zfill(6)
                    industry_name = str(row.get('industry', ''))
                    if stock_code and industry_name:
                        _sw_industry_map[stock_code] = industry_name
                
                if _sw_industry_map:
                    logger.info(f'行业分类获取成功，共 {len(_sw_industry_map)} 只股票')
                    return _sw_industry_map.copy()
                else:
                    logger.warning('行业分类获取失败，未获取到任何数据')
                    return {}
                    
            except Exception as e:
                logger.error(f'获取行业分类失败: {e}')
                return {}
            finally:
                self._logout()
        
        # 如果不使用行业分类，返回空dict
        return {}
    
    @retry_on_failure(max_retries=3)
    def get_stock_industry_sw(self, stock_code):
        """获取股票行业信息（使用 BaoStock）
        
        Args:
            stock_code: 股票代码
            
        Returns:
            行业名称，如果获取失败则返回空字符串
        """
        global _sw_industry_map
        
        # 先检查缓存
        if stock_code in _sw_industry_map:
            return _sw_industry_map[stock_code]
        
        # 尝试通过 BaoStock 获取单个股票的行业信息
        self._wait_if_needed()
        try:
            # 登录
            if not self._login():
                raise Exception('BaoStock 登录失败')
            
            # 获取行业分类
            rs = bs.query_stock_industry()
            if rs.error_code != '0':
                raise Exception(rs.error_msg)
            
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            if data_list:
                # 转换为 DataFrame
                industry_df = pd.DataFrame(data_list, columns=rs.fields)
                
                # 查找行业信息
                for _, row in industry_df.iterrows():
                    if str(row.get('code', '')).zfill(6) == stock_code:
                        industry_name = str(row.get('industry', ''))
                        # 请求完成后随机睡眠
                        self._random_sleep()
                        # 存入缓存
                        _sw_industry_map[stock_code] = industry_name
                        return industry_name
        except Exception as e:
            logger.debug(f'获取{stock_code}行业信息失败: {e}')
        finally:
            self._logout()
        
        return ''
    
    def clear_industry_cache(self):
        """清除行业缓存"""
        global _sw_industry_map
        _sw_industry_map.clear()
        logger.info('行业缓存已清除')
    
    @retry_on_failure(max_retries=3)
    def get_ths_industry_summary(self):
        """获取行业板块概要数据（使用 BaoStock）
        
        注意：BaoStock 没有直接提供同花顺行业板块数据，
        此处使用 query_stock_industry 接口获取行业分类数据作为替代。
        
        Returns:
            DataFrame with columns: code, name, industry, ...
        """
        self._wait_if_needed()
        try:
            # 登录
            if not self._login():
                raise Exception('BaoStock 登录失败')
            
            logger.info('开始通过 BaoStock 获取行业板块数据...')
            
            # 获取行业分类
            rs = bs.query_stock_industry()
            if rs.error_code != '0':
                raise Exception(rs.error_msg)
            
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                logger.warning('BaoStock 返回的行业板块数据为空')
                return pd.DataFrame()
            
            # 转换为 DataFrame
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            logger.info(f'获取行业板块数据成功，共 {len(df)} 条记录')
            # 请求完成后随机睡眠
            self._random_sleep(min_sleep=1.0, max_sleep=2.0)
            return df
        except Exception as e:
            logger.error(f'获取行业板块数据失败: {e}')
            raise  # 让重试装饰器处理
        finally:
            self._logout()
    
    @retry_on_failure(max_retries=3)
    def get_ths_industry_name_list(self):
        """获取行业板块名称列表（使用 BaoStock）
        
        注意：BaoStock 没有直接提供行业板块名称列表，
        此处从 query_stock_industry 接口获取行业分类数据，
        然后提取不重复的行业名称。
        
        Returns:
            DataFrame with columns: name, code (行业名称和相关代码)
        """
        self._wait_if_needed()
        try:
            # 登录
            if not self._login():
                raise Exception('BaoStock 登录失败')
            
            logger.info('开始通过 BaoStock 获取行业板块名称列表...')
            
            # 获取行业分类
            rs = bs.query_stock_industry()
            if rs.error_code != '0':
                raise Exception(rs.error_msg)
            
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                logger.warning('BaoStock 返回的行业板块数据为空')
                return pd.DataFrame()
            
            # 转换为 DataFrame
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            # 提取不重复的行业名称
            if 'industry' in df.columns:
                industry_list = df['industry'].unique()
                result_df = pd.DataFrame({
                    'name': industry_list,
                    'code': range(len(industry_list))
                })
                logger.info(f'获取行业板块名称列表成功，共 {len(result_df)} 个行业')
                # 请求完成后随机睡眠
                self._random_sleep(min_sleep=1.0, max_sleep=2.0)
                return result_df
            else:
                logger.warning('行业板块数据中没有 industry 列')
                return pd.DataFrame()
        except Exception as e:
            logger.error(f'获取行业板块名称列表失败: {e}')
            raise  # 让重试装饰器处理
        finally:
            self._logout()