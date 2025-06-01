#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""技术指标计算模块

此模块实现了常用的技术分析指标计算，包括：
1. 移动平均线（MA）
2. 相对强弱指数（RSI）
3. 移动平均收敛散度（MACD）
4. 布林带（Bollinger Bands）
5. 成交量加权平均价格（VWAP）
"""

import numpy as np
import pandas as pd
from typing import Union, Tuple

def calculate_ma(prices: Union[pd.Series, np.ndarray], period: int) -> np.ndarray:
    """计算移动平均线

    Args:
        prices: 价格序列
        period: 计算周期

    Returns:
        np.ndarray: 移动平均线值
    """
    if isinstance(prices, pd.Series):
        prices = prices.values
    return pd.Series(prices).rolling(window=period).mean().values

def calculate_rsi(prices: Union[pd.Series, np.ndarray], period: int = 14) -> np.ndarray:
    """计算相对强弱指数

    Args:
        prices: 价格序列
        period: 计算周期，默认14

    Returns:
        np.ndarray: RSI值
    """
    if isinstance(prices, pd.Series):
        prices = prices.values
        
    deltas = np.diff(prices)
    seed = deltas[:period+1]
    up = seed[seed >= 0].sum()/period
    down = -seed[seed < 0].sum()/period
    rs = up/down
    rsi = np.zeros_like(prices)
    rsi[:period] = 100. - 100./(1. + rs)

    for i in range(period, len(prices)):
        delta = deltas[i-1]
        if delta > 0:
            upval = delta
            downval = 0.
        else:
            upval = 0.
            downval = -delta

        up = (up*(period-1) + upval)/period
        down = (down*(period-1) + downval)/period
        rs = up/down
        rsi[i] = 100. - 100./(1. + rs)

    return rsi

def calculate_macd(
    prices: Union[pd.Series, np.ndarray],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """计算MACD指标

    Args:
        prices: 价格序列
        fast_period: 快线周期，默认12
        slow_period: 慢线周期，默认26
        signal_period: 信号线周期，默认9

    Returns:
        Tuple[np.ndarray, np.ndarray, np.ndarray]: (MACD线, 信号线, 柱状图)
    """
    if isinstance(prices, pd.Series):
        prices = prices.values

    # 计算快线与慢线的指数移动平均
    ema_fast = pd.Series(prices).ewm(span=fast_period, adjust=False).mean()
    ema_slow = pd.Series(prices).ewm(span=slow_period, adjust=False).mean()
    
    # 计算MACD线
    macd_line = ema_fast - ema_slow
    
    # 计算信号线
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    
    # 计算柱状图
    histogram = macd_line - signal_line
    
    return macd_line.values, signal_line.values, histogram.values

def calculate_bollinger_bands(
    prices: Union[pd.Series, np.ndarray],
    period: int = 20,
    num_std: float = 2.0
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """计算布林带

    Args:
        prices: 价格序列
        period: 计算周期，默认20
        num_std: 标准差倍数，默认2.0

    Returns:
        Tuple[np.ndarray, np.ndarray, np.ndarray]: (上轨, 中轨, 下轨)
    """
    if isinstance(prices, pd.Series):
        prices = prices.values
        
    # 计算中轨（简单移动平均线）
    middle_band = calculate_ma(prices, period)
    
    # 计算标准差
    rolling_std = pd.Series(prices).rolling(window=period).std()
    
    # 计算上下轨
    upper_band = middle_band + (rolling_std * num_std)
    lower_band = middle_band - (rolling_std * num_std)
    
    return upper_band, middle_band, lower_band

def calculate_vwap(
    prices: Union[pd.Series, np.ndarray],
    volumes: Union[pd.Series, np.ndarray]
) -> np.ndarray:
    """计算成交量加权平均价格

    Args:
        prices: 价格序列
        volumes: 成交量序列

    Returns:
        np.ndarray: VWAP值
    """
    if isinstance(prices, pd.Series):
        prices = prices.values
    if isinstance(volumes, pd.Series):
        volumes = volumes.values
        
    return np.cumsum(prices * volumes) / np.cumsum(volumes)