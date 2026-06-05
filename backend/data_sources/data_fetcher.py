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
        """获取股票列表，优先使用 AKShare，失败则用 BaoStock
        
        注意：此方法使用实时行情接口，建议在交易时段使用。
        非交易时段建议使用 get_stock_list_from_history() 方法。
        """
        logger.info('开始获取股票列表...')
        
        # 优先使用 AKShare
        try:
            df = self.ak_client.get_a_stock_list()
            if not df.empty and len(df) > 0:
                logger.info(f'AKShare 获取股票列表成功，共 {len(df)} 只')
                return df
            else:
                logger.warning('AKShare 返回的股票列表为空，尝试 BaoStock')
        except Exception as e:
            logger.warning(f'AKShare 获取股票列表失败，尝试 BaoStock: {e}')
        
        # 使用 BaoStock 作为备用
        try:
            df = self.bs_client.get_stock_list()
            if not df.empty and len(df) > 0:
                logger.info(f'BaoStock 获取股票列表成功，共 {len(df)} 只')
                return df
            else:
                logger.warning('BaoStock 返回的股票列表为空')
        except Exception as e:
            logger.error(f'BaoStock 获取股票列表也失败: {e}')
        
        logger.error('所有数据源均无法获取股票列表')
        return pd.DataFrame()
    
    def get_stock_list_from_history(self, trade_date=None):
        """通过历史数据接口获取股票列表（推荐非交易时段使用）
        
        此方法通过历史数据接口获取股票列表，相比实时行情接口更稳定，
        适合每天23点等定时任务使用。如果 AKShare 失败，会尝试使用 BaoStock。
        
        Args:
            trade_date: 交易日期，格式 YYYYMMDD 或 YYYY-MM-DD，默认为昨天
            
        Returns:
            DataFrame: 包含 code, name 等列的 DataFrame
        """
        logger.info(f'开始通过历史数据接口获取股票列表 (trade_date={trade_date})...')
        
        # 优先使用 AKShare 的历史数据接口
        try:
            df = self.ak_client.get_stock_list_from_history(trade_date=trade_date)
            if not df.empty and len(df) > 0:
                logger.info(f'AKShare 历史数据接口获取股票列表成功，共 {len(df)} 只')
                return df
            else:
                logger.warning('AKShare 历史数据接口返回的股票列表为空，尝试备用方案')
        except Exception as e:
            logger.warning(f'AKShare 历史数据接口获取股票列表失败，尝试备用方案: {e}')
        
        # 如果指定了交易日期，使用 BaoStock 获取该日期的数据
        if trade_date is not None:
            try:
                # 格式化日期
                if '-' in str(trade_date):
                    formatted_date = trade_date.replace('-', '')
                else:
                    formatted_date = str(trade_date)
                
                # 获取沪深两市数据
                df_sh = self.bs_client.get_daily_data('sh', formatted_date, formatted_date)
                df_sz = self.bs_client.get_daily_data('sz', formatted_date, formatted_date)
                df = pd.concat([df_sh, df_sz], ignore_index=True)
                
                if not df.empty and len(df) > 0:
                    logger.info(f'BaoStock 获取股票列表成功，共 {len(df)} 只')
                    return df
            except Exception as e:
                logger.warning(f'BaoStock 获取股票列表失败: {e}')
        
        logger.error('所有数据源均无法获取股票列表')
        return pd.DataFrame()
    
    def get_daily_data(self, stock_code, start_date, end_date=None):
        """获取股票日线数据，优先使用 AKShare"""
        logger.debug(f'获取 {stock_code} 日线数据，日期范围: {start_date} ~ {end_date}')
        
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
        """BaoStock 格式: sh.600000 / sz.000001"""
        if code.startswith('6'):
            return f'sh.{code}'
        else:
            return f'sz.{code}'
    
    def get_all_stocks_daily(self, trade_date=None):
        """获取所有股票的日行情数据
        
        注意：这个函数用于获取全市场股票的实时/盘后行情
        如果 AKShare 失败，返回空 DataFrame（调用方需要处理）
        """
        logger.info(f'开始获取全市场股票行情数据 (trade_date={trade_date})...')
        
        try:
            df = self.ak_client.get_a_stock_list()
            if not df.empty and len(df) > 0:
                logger.info(f'获取全部股票行情成功，共 {len(df)} 只')
                return df
            else:
                logger.warning('AKShare 返回的股票行情为空')
        except Exception as e:
            logger.error(f'获取全部股票行情失败: {e}')
        
        # 注意：BaoStock 不支持一次性获取全市场行情，所以这里不备用
        logger.warning('无法获取全市场股票行情，建议稍后重试')
        return pd.DataFrame()
    
    def get_industry_mapping(self):
        """获取股票行业映射（专门用于 data_service 调用）
        
        Returns:
            dict: {stock_code: industry_name}
        """
        logger.info('开始获取股票行业映射...')
        try:
            result = self.ak_client.get_industry_classification(use_sw_second=True)
            if isinstance(result, dict) and result:
                logger.info(f'获取股票行业映射成功，共 {len(result)} 只股票')
                return result
            else:
                logger.warning('行业映射为空或格式不正确')
        except Exception as e:
            logger.error(f'获取股票行业映射失败: {e}')
        
        return {}
    
    def get_ths_industry_summary(self):
        """获取同花顺行业板块概要数据
        
        Returns:
            DataFrame: 同花顺行业板块数据，包含涨跌幅、成交量等信息
        """
        logger.info('开始获取同花顺行业板块概要数据...')
        try:
            df = self.ak_client.get_ths_industry_summary()
            if not df.empty:
                logger.info(f'获取同花顺行业板块概要数据成功，共 {len(df)} 个行业')
                return df
            else:
                logger.warning('同花顺行业板块概要数据为空')
        except Exception as e:
            logger.error(f'获取同花顺行业板块概要数据失败: {e}')
        
        return pd.DataFrame()
    
    def get_ths_industry_name_list(self):
        """获取同花顺行业板块名称列表
        
        Returns:
            DataFrame: 包含 name 和 code 列的行业列表
        """
        logger.info('开始获取同花顺行业板块名称列表...')
        try:
            df = self.ak_client.get_ths_industry_name_list()
            if not df.empty:
                logger.info(f'获取同花顺行业板块名称列表成功，共 {len(df)} 个行业')
                return df
            else:
                logger.warning('同花顺行业板块名称列表为空')
        except Exception as e:
            logger.error(f'获取同花顺行业板块名称列表失败: {e}')
        
        return pd.DataFrame()
    
    def cleanup(self):
        """清理资源"""
        try:
            self.bs_client.logout()
        except Exception as e:
            logger.warning(f'BaoStock 登出失败: {e}')