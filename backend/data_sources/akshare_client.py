import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import logging
import time
import random
import threading

logger = logging.getLogger(__name__)

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
    
    def _random_sleep(self):
        """请求完成后随机睡眠，进一步降低被封风险"""
        sleep_time = random.uniform(0.5, 1.5)
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
            # 请求完成后随机睡眠
            self._random_sleep()
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
            # 请求完成后随机睡眠
            self._random_sleep()
            return df
        except Exception as e:
            logger.error(f'获取{stock_code}历史数据失败: {e}')
            return pd.DataFrame()
    
    def get_sw_second_industry(self):
        """获取申万二级行业基本信息（串行 + 限频）
        
        Returns:
            DataFrame with columns: index_code, index_name, stock_count, etc.
        """
        self._wait_if_needed()
        try:
            df = ak.sw_index_second_info()
            logger.info(f'获取申万二级行业信息成功，共 {len(df)} 个行业')
            # 请求完成后随机睡眠
            self._random_sleep()
            return df
        except Exception as e:
            logger.error(f'获取申万二级行业信息失败: {e}')
            return pd.DataFrame()
    
    def get_sw_second_industry_stocks(self, index_code=None):
        """获取申万二级行业成分股
        
        Args:
            index_code: 申万二级行业指数代码，如果为None则获取所有行业的成分股
            
        Returns:
            DataFrame with columns: index_code, stock_code, stock_name, etc.
        """
        self._wait_if_needed()
        try:
            # 获取申万二级行业成分股
            df = ak.sw_index_second_cons(index_code=index_code)
            # 请求完成后随机睡眠
            self._random_sleep()
            return df
        except Exception as e:
            logger.error(f'获取申万二级行业成分股失败: {e}')
            return pd.DataFrame()
    
    def get_industry_classification(self, use_sw_second=True):
        """获取行业分类（串行 + 限频）
        
        Args:
            use_sw_second: 是否使用申万二级行业，默认为True
            
        Returns:
            如果 use_sw_second=True，返回 dict: {stock_code: industry_name}
            否则返回原始的申万行业分类DataFrame
        """
        global _sw_industry_map
        
        if use_sw_second:
            # 如果缓存中有数据，直接返回
            if _sw_industry_map:
                return _sw_industry_map.copy()
            
            self._wait_if_needed()
            try:
                # 获取申万二级行业成分股（不指定index_code则获取所有）
                df = ak.sw_index_second_cons()
                
                if not df.empty:
                    # 建立股票代码到行业的映射
                    for _, row in df.iterrows():
                        stock_code = str(row.get('成分股代码', row.get('stock_code', ''))).zfill(6)
                        industry_name = row.get('申万行业二级', row.get('index_name', ''))
                        if stock_code and industry_name:
                            _sw_industry_map[stock_code] = industry_name
                    
                    logger.info(f'获取申万二级行业分类成功，共 {len(_sw_industry_map)} 只股票')
                    return _sw_industry_map.copy()
            except Exception as e:
                logger.error(f'获取申万二级行业分类失败: {e}，尝试使用备用方法')
        
        # 备用方法：使用原有的API
        self._wait_if_needed()
        try:
            df = ak.stock_industry_category_sw()
            # 请求完成后随机睡眠
            self._random_sleep()
            return df
        except Exception as e:
            logger.error(f'获取申万行业分类失败: {e}')
            return pd.DataFrame() if not use_sw_second else {}
    
    def get_stock_industry_sw(self, stock_code):
        """获取股票行业信息（串行 + 限频）
        
        Args:
            stock_code: 股票代码
            
        Returns:
            申万二级行业名称，如果获取失败则返回空字符串
        """
        global _sw_industry_map
        
        # 先检查缓存
        if stock_code in _sw_industry_map:
            return _sw_industry_map[stock_code]
        
        # 如果缓存为空，先加载行业分类
        if not _sw_industry_map:
            self.get_industry_classification(use_sw_second=True)
            if stock_code in _sw_industry_map:
                return _sw_industry_map[stock_code]
        
        # 如果还是没有，尝试单独获取
        self._wait_if_needed()
        try:
            df = ak.stock_individual_info_em(symbol=stock_code)
            if not df.empty:
                # 查找行业信息
                for _, row in df.iterrows():
                    if '行业' in str(row.get('item', '')):
                        # 请求完成后随机睡眠
                        self._random_sleep()
                        return str(row.get('value', ''))
        except Exception as e:
            logger.error(f'获取{stock_code}行业信息失败: {e}')
        
        return ''
    
    def clear_industry_cache(self):
        """清除行业缓存"""
        global _sw_industry_map
        _sw_industry_map.clear()
        logger.info('申万二级行业缓存已清除')