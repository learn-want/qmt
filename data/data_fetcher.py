#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""数据获取模块

此模块负责从miniQMT平台获取行情数据，包括：
1. 历史K线数据
2. 实时行情数据
3. 基础数据（股票列表、交易日历等）
"""

import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from loguru import logger

from xtquant import xtdata
from xtquant.xttype import StockAccount

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
        
        # 初始化数据连接
        self._init_connection()
        
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
            
        except Exception as e:
            logger.error(f"数据连接初始化失败: {str(e)}")
            raise
    
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
            data = xtdata.get_market_data_ex(
                fields=[],
                stock_code=[code],
                period=period,
                count=count
            )
            return data
        except Exception as e:
            logger.error(f"获取历史数据失败 - 代码: {code}, 错误: {str(e)}")
            return {}
    
    def get_realtime_data(self, code: str) -> Dict[str, Any]:
        """获取实时行情数据

        Args:
            code: 股票代码

        Returns:
            Dict[str, Any]: 实时行情数据字典
        """
        try:
            data = xtdata.get_market_data_ex(
                fields=[],
                stock_code=[code],
                period='1d',
                count=1
            )
            return data
        except Exception as e:
            logger.error(f"获取实时行情失败 - 代码: {code}, 错误: {str(e)}")
            return {}
    
    def get_trading_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取交易日历

        Args:
            start_date: 开始日期，格式：YYYY-MM-DD
            end_date: 结束日期，格式：YYYY-MM-DD

        Returns:
            List[str]: 交易日列表
        """
        try:
            dates = xtdata.get_trading_dates(
                start_date=start_date,
                end_date=end_date
            )
            return dates
        except Exception as e:
            logger.error(f"获取交易日历失败: {str(e)}")
            return []
    
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