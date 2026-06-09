import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import logging
import time
import random
import threading
import signal
from functools import wraps

logger = logging.getLogger(__name__)

# 请求超时设置（秒）
REQUEST_TIMEOUT = 30  # 单个请求超时时间

# 全局锁，确保 AKShare 所有操作串行执行（同一时间只有一个请求）
_api_lock = threading.Lock()
# 上次请求时间（用于限频）
_last_request_time = 0
# 随机延时范围（秒），模拟人工操作，避免被封
_MIN_DELAY = 1.5  # 最小延时
_MAX_DELAY = 3.5  # 最大延时

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
    """AKShare 数据客户端，所有 API 调用均串行执行并限频"""
    
    def __init__(self):
        pass
    
    @classmethod
    def _wait_if_needed(cls):
        """限频等待：使用随机延时，模拟人工操作，避免被封"""
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
            logger.debug(f'AKShare 限频等待: {sleep_time:.2f}秒 (随机范围: {_MIN_DELAY}-{_MAX_DELAY}秒)')
            time.sleep(sleep_time)
    
    def _random_sleep(self, min_sleep=1.0, max_sleep=3.0):
        """请求完成后随机睡眠，模拟人工操作，降低被封风险
        
        Args:
            min_sleep: 最小睡眠秒数，默认1.0秒
            max_sleep: 最大睡眠秒数，默认3.0秒
        """
        sleep_time = random.uniform(min_sleep, max_sleep)
        logger.debug(f'请求完成后随机睡眠 {sleep_time:.2f} 秒')
        time.sleep(sleep_time)
    
    @retry_on_failure(max_retries=3)
    def get_a_stock_list(self):
        """获取A股列表（串行 + 限频 + 重试）
        
        注意：此方法调用实时行情接口，建议在交易时段使用。
        非交易时段建议使用 get_stock_list_from_history() 方法。
        """
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
            # 请求完成后随机睡眠，使用较长间隔避免被限流
            self._random_sleep(min_sleep=2.0, max_sleep=4.0)
            return df
        except Exception as e:
            logger.error(f'获取A股列表失败: {e}')
            raise  # 让重试装饰器处理
    
    @retry_on_failure(max_retries=3, base_delay=10)  # 增加基础延迟到10秒
    def get_stock_list_from_history(self, trade_date=None):
        """通过历史数据接口获取A股列表（推荐非交易时段使用）
        
        此方法通过调用 stock_zh_a_spot_em 接口获取全市场股票数据，
        相比 stock_zh_a_hist 接口更稳定，适合每天23点等定时任务使用。
        
        Args:
            trade_date: 交易日期，格式 YYYYMMDD 或 YYYY-MM-DD，默认为昨天
            
        Returns:
            DataFrame with columns: code, name, ... (包含基本股票信息)
        """
        self._wait_if_needed()
        try:
            # 方案1: 使用实时行情接口（更稳定）
            # stock_zh_a_spot_em 接口相对稳定，限流较宽松
            logger.info('开始通过 stock_zh_a_spot_em 接口获取股票列表...')
            
            # 设置超时保护
            import socket
            original_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(REQUEST_TIMEOUT)
            
            try:
                df = ak.stock_zh_a_spot_em()
            finally:
                socket.setdefaulttimeout(original_timeout)
            
            if df.empty:
                logger.warning('stock_zh_a_spot_em 接口返回为空，尝试备用方案')
                # 方案2: 使用历史数据接口（作为备用）
                df = self._get_stock_list_from_history_backup(trade_date)
            
            if df.empty:
                logger.warning('所有方案均未获取到数据')
                return pd.DataFrame()
            
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
            
            # 确保 code 列为字符串且填充为6位
            df['code'] = df['code'].astype(str).str.zfill(6)
            
            logger.info(f'获取股票列表成功，共 {len(df)} 只')
            self._random_sleep(min_sleep=2.0, max_sleep=4.0)
            return df
            
        except Exception as e:
            logger.error(f'获取股票列表失败: {e}')
            raise  # 让重试装饰器处理
    
    def _get_stock_list_from_history_backup(self, trade_date=None):
        """备用方案：通过历史数据接口获取股票列表
        
        此方法作为 stock_zh_a_spot_em 接口的备用方案，
        通过调用 stock_zh_a_hist 接口获取指定日期的数据。
        
        Args:
            trade_date: 交易日期，格式 YYYYMMDD 或 YYYY-MM-DD，默认为昨天
            
        Returns:
            DataFrame with columns: code, name, ... (包含基本股票信息)
        """
        try:
            # 如果没有指定日期，默认使用昨天
            if trade_date is None:
                yesterday = datetime.now() - timedelta(days=1)
                trade_date = yesterday.strftime('%Y%m%d')
            else:
                # 统一日期格式为 YYYYMMDD
                trade_date = trade_date.replace('-', '') if '-' in str(trade_date) else str(trade_date)
            
            logger.info(f'开始通过 stock_zh_a_hist 接口获取历史数据 (trade_date={trade_date})...')
            
            # 设置超时保护
            import socket
            original_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(REQUEST_TIMEOUT)
            
            try:
                # 获取沪深两市所有股票的历史数据（指定日期）
                # 使用 adjust='' 不复权，获取原始数据
                df_sh = ak.stock_zh_a_hist(
                    symbol='sh',
                    period='daily',
                    start_date=trade_date,
                    end_date=trade_date,
                    adjust=''
                )
                self._random_sleep(min_sleep=1.5, max_sleep=3.0)
                
                df_sz = ak.stock_zh_a_hist(
                    symbol='sz',
                    period='daily',
                    start_date=trade_date,
                    end_date=trade_date,
                    adjust=''
                )
            finally:
                socket.setdefaulttimeout(original_timeout)
            
            # 合并数据
            df = pd.concat([df_sh, df_sz], ignore_index=True)
            
            if df.empty:
                logger.warning(f'历史数据接口未获取到 {trade_date} 的数据，可能该日非交易日')
                return pd.DataFrame()
            
            # 重命名列以匹配我们的格式
            df = df.rename(columns={
                '日期': 'date',
                '代码': 'code',
                '名称': 'name',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount',
                '涨跌幅': 'pct_change',
                '涨跌额': 'change',
                '换手率': 'turnover_rate'
            })
            
            logger.info(f'通过历史数据接口获取股票列表成功，共 {len(df)} 只 (trade_date={trade_date})')
            return df
            
        except Exception as e:
            logger.error(f'备用方案获取股票列表失败: {e}')
            return pd.DataFrame()
    
    @retry_on_failure(max_retries=3)
    def get_stock_history(self, stock_code, period='daily', start_date=None, end_date=None):
        """获取股票历史数据（串行 + 限频 + 重试）"""
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
            # 请求完成后随机睡眠
            self._random_sleep(min_sleep=1.5, max_sleep=3.5)
            return df
        except Exception as e:
            logger.error(f'获取{stock_code}历史数据失败: {e}')
            raise  # 让重试装饰器处理
    
    @retry_on_failure(max_retries=3)
    def get_sw_second_industry(self):
        """获取申万二级行业基本信息（串行 + 限频 + 重试）
        
        Returns:
            DataFrame with columns: index_code, index_name, stock_count, etc.
        """
        self._wait_if_needed()
        try:
            # 使用正确的 API: sw_index_second_info 获取申万二级行业列表
            df = ak.sw_index_second_info()
            logger.info(f'获取申万二级行业信息成功，共 {len(df)} 个行业')
            # 请求完成后随机睡眠
            self._random_sleep(min_sleep=2.0, max_sleep=4.0)
            return df
        except Exception as e:
            logger.error(f'获取申万二级行业信息失败: {e}')
            raise  # 让重试装饰器处理
    
    def get_sw_second_industry_stocks(self, index_code=None):
        """获取申万二级行业成分股
        
        注意：ak.sw_index_second_cons 在新版 akshare 中不存在
        使用备用方案：通过 stock_individual_info_em 获取单个股票行业信息
        
        Args:
            index_code: 申万二级行业指数代码（当前版本忽略此参数）
            
        Returns:
            DataFrame with columns: index_code, stock_code, stock_name, etc.
        """
        logger.warning('get_sw_second_industry_stocks: 申万二级行业成分股API不可用，建议使用 get_industry_classification')
        return pd.DataFrame()
    
    @retry_on_failure(max_retries=3)
    def get_industry_classification(self, use_sw_second=True):
        """获取行业分类（串行 + 限频 + 重试）
        
        使用东方财富的行业板块数据：
        1. 使用 stock_board_industry_name_em() 获取行业列表
        2. 使用 stock_board_industry_cons_em(symbol=行业名称) 获取各行业的成分股
        
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
            
            # 使用东方财富的行业板块数据
            try:
                self._wait_if_needed()
                # 获取行业列表
                logger.info('开始获取东方财富行业板块数据...')
                industry_df = ak.stock_board_industry_name_em()
                
                if industry_df.empty:
                    logger.warning('东方财富行业列表为空')
                    return {}
                
                logger.info(f'获取到 {len(industry_df)} 个行业板块')
                
                # 遍历每个行业，获取成分股
                success_count = 0
                for idx, (_, ind_row) in enumerate(industry_df.iterrows()):
                    industry_name = ind_row.get('板块名称', '')
                    if not industry_name:
                        continue
                    
                    try:
                        # 限频等待
                        self._wait_if_needed()
                        
                        # 获取该行业的成分股
                        cons_df = ak.stock_board_industry_cons_em(symbol=industry_name)
                        
                        if not cons_df.empty:
                            for _, stock_row in cons_df.iterrows():
                                stock_code = str(stock_row.get('代码', '')).zfill(6)
                                if stock_code:
                                    _sw_industry_map[stock_code] = industry_name
                            success_count += 1
                            
                            # 每处理10个行业打印一次进度
                            if success_count % 10 == 0:
                                logger.info(f'已处理 {success_count}/{len(industry_df)} 个行业，获取 {len(_sw_industry_map)} 只股票')
                        
                        # 请求完成后随机睡眠，避免被限流
                        self._random_sleep(min_sleep=1.0, max_sleep=2.0)
                        
                    except Exception as e:
                        logger.debug(f'获取行业 {industry_name} 成分股失败: {e}')
                        continue
                
                if _sw_industry_map:
                    logger.info(f'行业分类获取成功，共 {len(_sw_industry_map)} 只股票，处理了 {success_count} 个行业')
                    return _sw_industry_map.copy()
                else:
                    logger.warning('行业分类获取失败，未获取到任何数据')
                    return {}
                    
            except Exception as e:
                logger.error(f'获取行业分类失败: {e}')
                return {}
        
        # 如果不使用行业分类，返回空dict
        return {}
    
    @retry_on_failure(max_retries=3)
    def get_stock_industry_sw(self, stock_code):
        """获取股票行业信息（串行 + 限频 + 重试）
        
        Args:
            stock_code: 股票代码
            
        Returns:
            申万二级行业名称，如果获取失败则返回空字符串
        """
        global _sw_industry_map
        
        # 先检查缓存
        if stock_code in _sw_industry_map:
            return _sw_industry_map[stock_code]
        
        # 尝试通过东方财富获取单个股票的行业信息
        self._wait_if_needed()
        try:
            df = ak.stock_individual_info_em(symbol=stock_code)
            if not df.empty:
                # 查找行业信息
                for _, row in df.iterrows():
                    item = str(row.get('item', ''))
                    if '行业' in item or '行业' in item:
                        industry_name = str(row.get('value', ''))
                        # 请求完成后随机睡眠
                        self._random_sleep()
                        # 存入缓存
                        _sw_industry_map[stock_code] = industry_name
                        return industry_name
        except Exception as e:
            logger.debug(f'获取{stock_code}行业信息失败: {e}')
        
        return ''
    
    def clear_industry_cache(self):
        """清除行业缓存"""
        global _sw_industry_map
        _sw_industry_map.clear()
        logger.info('申万二级行业缓存已清除')
    
    @retry_on_failure(max_retries=3)
    def get_ths_industry_summary(self):
        """获取同花顺行业板块概要数据（用于展示）
        
        使用 stock_board_industry_summary_ths 接口获取同花顺行业板块数据
        
        Returns:
            DataFrame with columns: 序号, 板块, 涨跌幅, 总成交量, 总成交额, 
            净流入, 上涨家数, 下跌家数, 均价, 领涨股, 领涨股-最新价, 领涨股-涨跌幅
        """
        self._wait_if_needed()
        try:
            df = ak.stock_board_industry_summary_ths()
            logger.info(f'获取同花顺行业板块数据成功，共 {len(df)} 个行业')
            # 请求完成后随机睡眠
            self._random_sleep(min_sleep=2.0, max_sleep=3.0)
            return df
        except Exception as e:
            logger.error(f'获取同花顺行业板块数据失败: {e}')
            raise  # 让重试装饰器处理
    
    @retry_on_failure(max_retries=3)
    def get_ths_industry_name_list(self):
        """获取同花顺行业板块名称列表
        
        使用 stock_board_industry_name_ths 接口获取同花顺行业板块列表
        
        Returns:
            DataFrame with columns: name, code
        """
        self._wait_if_needed()
        try:
            df = ak.stock_board_industry_name_ths()
            logger.info(f'获取同花顺行业板块列表成功，共 {len(df)} 个行业')
            # 请求完成后随机睡眠
            self._random_sleep(min_sleep=1.0, max_sleep=2.0)
            return df
        except Exception as e:
            logger.error(f'获取同花顺行业板块列表失败: {e}')
            raise  # 让重试装饰器处理