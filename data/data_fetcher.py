#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""数据获取模块

此模块负责从miniQMT平台获取行情数据，包括：
1. 历史K线数据
2. 实时行情数据
3. 基础数据（股票列表、交易日历等）
"""

import os
import time
import pickle
import functools
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from loguru import logger

from xtquant import xtdata
from xtquant.xttype import StockAccount

def retry(max_attempts: int = 3, delay: float = 1.0):
    """重试装饰器

    Args:
        max_attempts: 最大尝试次数
        delay: 重试延迟时间（秒）

    Returns:
        Callable: 装饰后的函数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts == max_attempts:
                        logger.error(f"函数 {func.__name__} 执行失败，已重试 {attempts} 次: {str(e)}")
                        raise
                    logger.warning(f"函数 {func.__name__} 执行失败，正在重试 ({attempts}/{max_attempts}): {str(e)}")
                    time.sleep(delay * attempts)  # 指数退避
        return wrapper
    return decorator


def cache_data(cache_dir: str, expire_seconds: int = 86400):
    """数据缓存装饰器

    Args:
        cache_dir: 缓存目录
        expire_seconds: 缓存过期时间（秒），默认1天

    Returns:
        Callable: 装饰后的函数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 创建缓存目录
            os.makedirs(cache_dir, exist_ok=True)
            
            # 生成缓存文件名
            cache_key = f"{func.__name__}_{hash(str(args) + str(kwargs))}.pkl"
            cache_file = os.path.join(cache_dir, cache_key)
            
            # 检查缓存是否存在且未过期
            if os.path.exists(cache_file):
                file_time = os.path.getmtime(cache_file)
                if time.time() - file_time < expire_seconds:
                    try:
                        with open(cache_file, 'rb') as f:
                            logger.debug(f"从缓存加载数据: {cache_file}")
                            return pickle.load(f)
                    except Exception as e:
                        logger.warning(f"读取缓存失败: {str(e)}")
            
            # 执行原函数
            result = func(*args, **kwargs)
            
            # 保存结果到缓存
            try:
                with open(cache_file, 'wb') as f:
                    pickle.dump(result, f)
                    logger.debug(f"数据已缓存: {cache_file}")
            except Exception as e:
                logger.warning(f"缓存数据失败: {str(e)}")
                
            return result
        return wrapper
    return decorator


class DataFetcher:
    """数据获取类"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化数据获取器

        Args:
            config: 配置参数字典
        """
        self.config = config
        self.universe = config['data']['universe']
        self.history_length = config['data']['history_length']
        
        # 缓存设置
        self.data_dir = config.get('data_dir', 'data')
        self.cache_dir = os.path.join(self.data_dir, 'cache')
        self.cache_expire = config.get('cache_expire', 86400)  # 默认缓存1天
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # 初始化数据连接
        self._init_connection()
        
    @retry(max_attempts=3, delay=2.0)
    def _init_connection(self) -> None:
        """初始化与行情服务器的连接"""
        try:
            # 下载本地历史数据
            for code in self.universe:
                xtdata.download_history_data(code, period='1d', incrementally=True)
            logger.info("历史数据下载完成")
            
            # 订阅实时行情
            for code in self.universe:
                xtdata.subscribe_quote(code, period='1d')
            time.sleep(1)  # 等待订阅完成
            logger.info("实时行情订阅完成")
            
            # 验证连接状态
            self._check_connection_status()
            
        except Exception as e:
            logger.error(f"数据连接初始化失败: {str(e)}")
            raise
    
    def _check_connection_status(self) -> bool:
        """检查连接状态

        Returns:
            bool: 连接是否正常
        """
        try:
            # 简单测试API是否可用
            test_code = self.universe[0] if self.universe else "000001.SZ"
            test_data = xtdata.get_market_data_ex(
                field_list=["close"],
                stock_list=[test_code],
                period='1d',
                count=1
            )
            return len(test_data) > 0
        except Exception as e:
            logger.error(f"连接状态检查失败: {str(e)}")
            return False
    
    @retry(max_attempts=3, delay=1.0)
    @cache_data(cache_dir=os.path.join(os.getcwd(), 'data', 'cache', 'history'))
    def get_history_data(self, code: str, period: str = '1d', count: int = -1) -> Dict[str, Any]:
        """获取历史K线数据

        Args:
            code: 股票代码
            period: 周期，默认日线
            count: 获取条数，默认全部

        Returns:
            Dict[str, Any]: K线数据字典
        """
        try:
            logger.debug(f"获取历史数据 - 代码: {code}, 周期: {period}, 条数: {count}")
            data = xtdata.get_market_data_ex(
                field_list=[],
                stock_list=[code],
                period=period,
                count=count
            )
            if not data or not data.get(code):
                logger.warning(f"获取历史数据为空 - 代码: {code}")
                return {}
                
            return data
        except Exception as e:
            logger.error(f"获取历史数据失败 - 代码: {code}, 错误: {str(e)}")
            return {}
    
    @retry(max_attempts=3, delay=0.5)
    def get_realtime_data(self, code: str) -> Dict[str, Any]:
        """获取实时行情数据

        Args:
            code: 股票代码

        Returns:
            Dict[str, Any]: 实时行情数据字典
        """
        try:
            logger.debug(f"获取实时行情 - 代码: {code}")
            data = xtdata.get_market_data_ex(
                field_list=[],
                stock_list=[code],
                period='1d',
                count=1
            )
            if not data or not data.get(code):
                logger.warning(f"获取实时行情为空 - 代码: {code}")
                return {}
                
            return data
        except Exception as e:
            logger.error(f"获取实时行情失败 - 代码: {code}, 错误: {str(e)}")
            return {}
    
    @retry(max_attempts=3, delay=1.0)
    @cache_data(cache_dir=os.path.join(os.getcwd(), 'data', 'cache', 'calendar'))
    def get_trading_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取交易日历

        Args:
            start_date: 开始日期，格式：YYYY-MM-DD
            end_date: 结束日期，格式：YYYY-MM-DD

        Returns:
            List[str]: 交易日列表
        """
        try:
            # 转换日期格式
            # start = datetime.strptime(start_date, "%Y%m%d")
            # end = datetime.strptime(end_date, "%Y%m%d")
            start=start_date
            end=end_date
            # start='20250101'
            # end='20250910'
            print(start,end)
            
            # 获取交易日历
            dates = xtdata.get_trading_dates("SH", start, end)
            
            # 转换为字符串格式
            # date_strs = [date.strftime("%Y%m%d") for date in dates]
            date_strs=list(set(dates))
            if not date_strs:
                logger.warning(f"获取的交易日历为空: {start_date} 至 {end_date}")
            
            return date_strs
            
        except Exception as e:
            logger.error(f"获取交易日历失败: {str(e)}")
            return []
    
    @retry(max_attempts=3, delay=2.0)
    @cache_data(cache_dir=os.path.join(os.getcwd(), 'data', 'cache', 'batch'))
    def get_batch_history_data(self, codes: List[str], period: str = '1d', count: int = -1) -> Dict[str, Dict[str, Any]]:
        """批量获取历史K线数据

        Args:
            codes: 股票代码列表
            period: 周期，默认日线
            count: 获取条数，默认全部

        Returns:
            Dict[str, Dict[str, Any]]: 多股票K线数据字典
        """
        try:
            logger.debug(f"批量获取历史数据 - 代码数量: {len(codes)}, 周期: {period}, 条数: {count}")
            data = xtdata.get_market_data_ex(
                field_list=[],
                stock_list=codes,
                period=period,
                count=count
            )
            
            # 验证数据完整性
            missing_codes = [code for code in codes if code not in data]
            if missing_codes:
                logger.warning(f"部分股票数据获取失败: {missing_codes}")
                
            return data
        except Exception as e:
            logger.error(f"批量获取历史数据失败: {str(e)}")
            return {}
    
    def validate_data(self, data: Dict[str, Any], code: str) -> bool:
        """验证数据有效性

        Args:
            data: 数据字典
            code: 股票代码

        Returns:
            bool: 数据是否有效
        """
        if not data or code not in data:
            return False
            
        stock_data = data[code]
        required_fields = ['time', 'open', 'high', 'low', 'close', 'volume']
        
        # 检查必要字段是否存在且非空
        for field in required_fields:
            if field not in stock_data or len(stock_data[field]) == 0:
                logger.warning(f"数据验证失败 - 代码: {code}, 缺少字段: {field}")
                return False
        
        return True
    
    def get_stock_list(self) -> List[str]:
        """获取股票列表

        Returns:
            List[str]: 股票代码列表
        """
        try:
            # 获取沪深A股列表
            sh_list = xtdata.get_stock_list_in_sector('沪深A股')
            return sh_list
        except Exception as e:
            logger.error(f"获取股票列表失败: {str(e)}")
            return []
    
    def get_stock_info(self, code: str) -> Dict[str, Any]:
        """获取股票基本信息

        Args:
            code: 股票代码

        Returns:
            Dict[str, Any]: 股票信息字典
        """
        try:
            info = xtdata.get_instrument_detail(code)
            return info
        except Exception as e:
            logger.error(f"获取股票信息失败 - 代码: {code}, 错误: {str(e)}")
            return {}
    
    def is_trading_time(self) -> bool:
        """判断当前是否为交易时段

        Returns:
            bool: 是否为交易时段
        """
        now = datetime.now().time()
        trading_hours = self.config['trading']['trading_hours']
        
        for start, end in trading_hours:
            start_time = datetime.strptime(start, "%H:%M").time()
            end_time = datetime.strptime(end, "%H:%M").time()
            if start_time <= now <= end_time:
                return True
        return False