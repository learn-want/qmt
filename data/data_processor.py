#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""数据处理模块

此模块负责处理和转换行情数据，包括：
1. 数据清洗和预处理
2. 技术指标计算
3. 特征工程
"""

import numpy as np
import pandas as pd
import os
import pickle
from functools import lru_cache
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from loguru import logger

from utils.indicators import (
    calculate_ma,
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
    calculate_vwap
)

def memoize_dataframe(func: Callable) -> Callable:
    """DataFrame结果缓存装饰器
    
    Args:
        func: 需要缓存结果的函数
        
    Returns:
        Callable: 包装后的函数
    """
    cache = {}
    
    def wrapper(*args, **kwargs):
        # 创建缓存键
        key = str(args) + str(kwargs)
        
        # 检查缓存
        if key in cache:
            logger.debug(f"使用缓存数据: {func.__name__}")
            return cache[key].copy()
            
        # 计算结果
        result = func(*args, **kwargs)
        
        # 缓存结果
        if isinstance(result, pd.DataFrame) and not result.empty:
            cache[key] = result.copy()
            
        return result
        
    return wrapper


class DataProcessor:
    """数据处理类"""

    def __init__(self, config: Dict[str, Any]):
        """初始化数据处理器

        Args:
            config: 配置参数字典
        """
        self.config = config
        self.indicators = config['data']['indicators']
        
        # 创建缓存目录
        self.cache_dir = os.path.join(os.getcwd(), 'data', 'cache', 'processed')
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_cache_path(self, stock_code: str) -> str:
        """获取缓存文件路径
        
        Args:
            stock_code: 股票代码
            
        Returns:
            str: 缓存文件路径
        """
        return os.path.join(self.cache_dir, f"{stock_code}.pkl")
    
    def save_to_cache(self, df: pd.DataFrame, stock_code: str) -> None:
        """保存数据到缓存
        
        Args:
            df: 数据框
            stock_code: 股票代码
        """
        try:
            cache_path = self.get_cache_path(stock_code)
            with open(cache_path, 'wb') as f:
                pickle.dump(df, f)
            logger.debug(f"数据已缓存: {stock_code}")
        except Exception as e:
            logger.error(f"缓存数据失败 - 代码: {stock_code}, 错误: {str(e)}")
    
    def load_from_cache(self, stock_code: str) -> Optional[pd.DataFrame]:
        """从缓存加载数据
        
        Args:
            stock_code: 股票代码
            
        Returns:
            Optional[pd.DataFrame]: 缓存的数据框，如果不存在则返回None
        """
        try:
            cache_path = self.get_cache_path(stock_code)
            if os.path.exists(cache_path):
                with open(cache_path, 'rb') as f:
                    df = pickle.load(f)
                logger.debug(f"从缓存加载数据: {stock_code}")
                return df
        except Exception as e:
            logger.error(f"加载缓存数据失败 - 代码: {stock_code}, 错误: {str(e)}")
        return None
    
    @memoize_dataframe
    def process_kline_data(self, data: Dict[str, Any]) -> pd.DataFrame:
        """处理K线数据

        Args:
            data: K线数据字典

        Returns:
            pd.DataFrame: 处理后的数据框
        """
        try:
            # 获取股票代码
            if not data:
                logger.warning("输入数据为空")
                return pd.DataFrame()
                
            stock_code = list(data.keys())[0]
            
            # 尝试从缓存加载
            cached_df = self.load_from_cache(stock_code)
            if cached_df is not None:
                return cached_df
            
            # 转换为DataFrame
            df = self._convert_to_dataframe(data)
            if df.empty:
                return df

            # 数据清洗
            df = self._clean_data(df)

            # 计算技术指标
            df = self._calculate_indicators(df)
            
            # 保存到缓存
            self.save_to_cache(df, stock_code)

            return df

        except Exception as e:
            logger.error(f"K线数据处理失败: {str(e)}")
            return pd.DataFrame()

    def _convert_to_dataframe(self, data: Dict[str, Any]) -> pd.DataFrame:
        """将字典数据转换为DataFrame

        Args:
            data: K线数据字典

        Returns:
            pd.DataFrame: 转换后的数据框
        """
        try:
            # 提取第一个股票的数据
            stock_code = list(data.keys())[0]
            stock_data = data[stock_code]

            df = pd.DataFrame({
                'datetime': pd.to_datetime(stock_data['time']),
                'open': stock_data['open'],
                'high': stock_data['high'],
                'low': stock_data['low'],
                'close': stock_data['close'],
                'volume': stock_data['volume'],
                'amount': stock_data['amount']
            })

            df.set_index('datetime', inplace=True)
            return df

        except Exception as e:
            logger.error(f"数据转换失败: {str(e)}")
            return pd.DataFrame()

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗数据

        Args:
            df: 原始数据框

        Returns:
            pd.DataFrame: 清洗后的数据框
        """
        try:
            # 删除重复数据
            df = df[~df.index.duplicated(keep='last')]

            # 按时间排序
            df.sort_index(inplace=True)

            # 填充缺失值
            df.fillna(method='ffill', inplace=True)

            # 计算涨跌幅
            df['returns'] = df['close'].pct_change()

            return df

        except Exception as e:
            logger.error(f"数据清洗失败: {str(e)}")
            return df

    @lru_cache(maxsize=32)
    def _get_indicator_params(self, indicator: str) -> Dict[str, Any]:
        """获取指标参数
        
        Args:
            indicator: 指标名称
            
        Returns:
            Dict[str, Any]: 指标参数
        """
        # 从配置中获取指标参数，如果没有则使用默认值
        indicator_config = self.config.get('indicators', {}).get(indicator, {})
        
        # 默认参数
        defaults = {
            'MA': {'periods': [5, 10, 20, 60]},
            'RSI': {'period': 14},
            'MACD': {'fast_period': 12, 'slow_period': 26, 'signal_period': 9},
            'BOLL': {'period': 20, 'std_dev': 2},
            'VWAP': {'period': 14}
        }
        
        # 合并默认参数和配置参数
        return {**defaults.get(indicator, {}), **indicator_config}
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标

        Args:
            df: 原始数据框

        Returns:
            pd.DataFrame: 添加技术指标后的数据框
        """
        try:
            # 创建数据副本以避免警告
            result_df = df.copy()
            
            # 并行计算所有指标
            for indicator in self.indicators:
                params = self._get_indicator_params(indicator)
                
                if indicator == 'MA':
                    # 计算多个周期的移动平均线
                    periods = params['periods']
                    for period in periods:
                        result_df[f'ma_{period}'] = calculate_ma(result_df['close'], period)

                elif indicator == 'RSI':
                    # 计算RSI指标
                    period = params['period']
                    result_df['rsi'] = calculate_rsi(result_df['close'], period)

                elif indicator == 'MACD':
                    # 计算MACD指标
                    fast_period = params['fast_period']
                    slow_period = params['slow_period']
                    signal_period = params['signal_period']
                    macd, signal, hist = calculate_macd(
                        result_df['close'], 
                        fast_period=fast_period, 
                        slow_period=slow_period, 
                        signal_period=signal_period
                    )
                    result_df['macd'] = macd
                    result_df['macd_signal'] = signal
                    result_df['macd_hist'] = hist

                elif indicator == 'BOLL':
                    # 计算布林带
                    period = params['period']
                    std_dev = params['std_dev']
                    upper, middle, lower = calculate_bollinger_bands(
                        result_df['close'], 
                        period=period, 
                        std_dev=std_dev
                    )
                    result_df['boll_upper'] = upper
                    result_df['boll_middle'] = middle
                    result_df['boll_lower'] = lower

                elif indicator == 'VWAP':
                    # 计算VWAP
                    period = params['period']
                    result_df['vwap'] = calculate_vwap(result_df['close'], result_df['volume'], period)

            return result_df

        except Exception as e:
            logger.error(f"技术指标计算失败: {str(e)}")
            return df

    def calculate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算特征

        Args:
            df: 原始数据框

        Returns:
            pd.DataFrame: 添加特征后的数据框
        """
        try:
            # 计算波动率
            df['volatility'] = df['returns'].rolling(window=20).std()

            # 计算成交量变化
            df['volume_ma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma']

            # 计算趋势强度
            df['trend_strength'] = abs(df['close'] - df['ma_20']) / df['ma_20']

            return df

        except Exception as e:
            logger.error(f"特征计算失败: {str(e)}")
            return df