#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试优化后的数据获取功能
"""
import logging
import sys
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def test_akshare_client():
    """测试 AKShare 客户端"""
    logger.info("=" * 50)
    logger.info("开始测试 AKShare 客户端...")
    logger.info("=" * 50)
    
    try:
        from data_sources.akshare_client import AKShareClient
        
        client = AKShareClient()
        
        # 测试获取股票列表
        logger.info("测试1: 获取股票列表 (get_stock_list_from_history)")
        df = client.get_stock_list_from_history()
        
        if not df.empty:
            logger.info(f"✅ 成功获取 {len(df)} 只股票")
            logger.info(f"列名: {df.columns.tolist()}")
            logger.info(f"前3条数据:\n{df.head(3)}")
        else:
            logger.warning("⚠️ 获取的数据为空")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_fetcher():
    """测试 DataFetcher"""
    logger.info("=" * 50)
    logger.info("开始测试 DataFetcher...")
    logger.info("=" * 50)
    
    try:
        from data_sources.data_fetcher import DataFetcher
        
        fetcher = DataFetcher()
        
        # 测试获取股票列表
        logger.info("测试2: 通过 DataFetcher 获取股票列表")
        df = fetcher.get_stock_list_from_history()
        
        if not df.empty:
            logger.info(f"✅ 成功获取 {len(df)} 只股票")
            logger.info(f"列名: {df.columns.tolist()}")
            logger.info(f"前3条数据:\n{df.head(3)}")
        else:
            logger.warning("⚠️ 获取的数据为空")
        
        # 清理资源
        fetcher.cleanup()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    logger.info("开始测试优化后的数据获取功能...")
    
    # 测试 AKShare 客户端
    result1 = test_akshare_client()
    
    # 测试 DataFetcher
    result2 = test_data_fetcher()
    
    # 总结
    logger.info("=" * 50)
    logger.info("测试总结:")
    logger.info(f"AKShare 客户端: {'✅ 通过' if result1 else '❌ 失败'}")
    logger.info(f"DataFetcher: {'✅ 通过' if result2 else '❌ 失败'}")
    logger.info("=" * 50)
    
    sys.exit(0 if (result1 and result2) else 1)
