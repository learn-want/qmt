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
from typing import Dict, List, Any, Optional
from loguru import logger

from utils.indicators import (
    calculate_ma,
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
    calculate_vwap
)

class DataProcessor:
    """数据处理类"""

    def __init__(self, config: Dict[str, Any]):
        """初始化数据处理器

        Args:
            config: 配置参数字典
        """
        self.config = config
        self.indicators = config['data']['indicators']

    def process_kline_data(self, data: Dict[str, Any]) -> pd.DataFrame:
        """处理K线数据

        Args:
            data: K线数据字典

        Returns:
            pd.DataFrame: 处理后的数据框
        """
        try:
            # 转换为DataFrame
            df = self._convert_to_dataframe(data)
            if df.empty:
                return df

            # 数据清洗
            df = self._clean_data(df)

            # 计算技术指标
            df = self._calculate_indicators(df)

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

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标

        Args:
            df: 原始数据框

        Returns:
            pd.DataFrame: 添加技术指标后的数据框
        """
        try:
            for indicator in self.indicators:
                if indicator == 'MA':
                    # 计算多个周期的移动平均线
                    periods = [5, 10, 20, 60]
                    for period in periods:
                        df[f'ma_{period}'] = calculate_ma(df['close'], period)

                elif indicator == 'RSI':
                    # 计算RSI指标
                    df['rsi'] = calculate_rsi(df['close'])

                elif indicator == 'MACD':
                    # 计算MACD指标
                    macd, signal, hist = calculate_macd(df['close'])
                    df['macd'] = macd
                    df['macd_signal'] = signal
                    df['macd_hist'] = hist

                elif indicator == 'BOLL':
                    # 计算布林带
                    upper, middle, lower = calculate_bollinger_bands(df['close'])
                    df['boll_upper'] = upper
                    df['boll_middle'] = middle
                    df['boll_lower'] = lower

                elif indicator == 'VWAP':
                    # 计算VWAP
                    df['vwap'] = calculate_vwap(df['close'], df['volume'])

            return df

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