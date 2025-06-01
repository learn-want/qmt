#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""性能评估模块

此模块实现了策略绩效评估的各项指标计算，包括：
1. 收益率分析
2. 风险评估
3. 绩效指标
4. 交易统计
"""

import numpy as np
import pandas as pd
from typing import Tuple
from loguru import logger

def calculate_returns(returns: pd.Series) -> float:
    """计算累计收益率

    Args:
        returns: 日收益率序列

    Returns:
        float: 累计收益率
    """
    try:
        return (1 + returns).prod() - 1
    except Exception as e:
        logger.error(f"计算累计收益率失败: {str(e)}")
        return 0.0

def calculate_drawdown(returns: pd.Series) -> float:
    """计算最大回撤

    Args:
        returns: 日收益率序列

    Returns:
        float: 最大回撤
    """
    try:
        # 计算累计收益
        cum_returns = (1 + returns).cumprod()
        
        # 计算历史最高点
        rolling_max = cum_returns.expanding(min_periods=1).max()
        
        # 计算回撤
        drawdowns = cum_returns / rolling_max - 1
        
        return abs(drawdowns.min())
    
    except Exception as e:
        logger.error(f"计算最大回撤失败: {str(e)}")
        return 0.0

def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.03, periods: int = 252) -> float:
    """计算夏普比率

    Args:
        returns: 日收益率序列
        risk_free_rate: 无风险利率，默认3%
        periods: 年化周期，日线为252

    Returns:
        float: 夏普比率
    """
    try:
        # 计算超额收益
        excess_returns = returns - risk_free_rate / periods
        
        # 计算年化夏普比率
        sharpe = np.sqrt(periods) * excess_returns.mean() / excess_returns.std()
        
        return sharpe
    
    except Exception as e:
        logger.error(f"计算夏普比率失败: {str(e)}")
        return 0.0

def calculate_alpha_beta(returns: pd.Series, benchmark_returns: pd.Series = None) -> Tuple[float, float]:
    """计算Alpha和Beta

    Args:
        returns: 策略收益率序列
        benchmark_returns: 基准收益率序列，默认使用沪深300

    Returns:
        Tuple[float, float]: (Alpha, Beta)
    """
    try:
        # 如果没有提供基准收益率，使用沪深300
        if benchmark_returns is None:
            # 这里应该从数据源获取沪深300收益率
            # 暂时返回默认值
            return 0.0, 1.0
        
        # 计算Beta
        covariance = np.cov(returns, benchmark_returns)[0][1]
        variance = np.var(benchmark_returns)
        beta = covariance / variance
        
        # 计算Alpha
        alpha = returns.mean() - beta * benchmark_returns.mean()
        
        return alpha, beta
    
    except Exception as e:
        logger.error(f"计算Alpha和Beta失败: {str(e)}")
        return 0.0, 1.0

def calculate_volatility(returns: pd.Series, periods: int = 252) -> float:
    """计算波动率

    Args:
        returns: 收益率序列
        periods: 年化周期，日线为252

    Returns:
        float: 年化波动率
    """
    try:
        return returns.std() * np.sqrt(periods)
    except Exception as e:
        logger.error(f"计算波动率失败: {str(e)}")
        return 0.0

def calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.03, periods: int = 252) -> float:
    """计算索提诺比率

    Args:
        returns: 收益率序列
        risk_free_rate: 无风险利率，默认3%
        periods: 年化周期，日线为252

    Returns:
        float: 索提诺比率
    """
    try:
        # 计算超额收益
        excess_returns = returns - risk_free_rate / periods
        
        # 计算下行波动率
        negative_returns = excess_returns[excess_returns < 0]
        downside_std = np.sqrt(np.mean(negative_returns ** 2))
        
        # 计算索提诺比率
        sortino = np.sqrt(periods) * excess_returns.mean() / downside_std
        
        return sortino
    
    except Exception as e:
        logger.error(f"计算索提诺比率失败: {str(e)}")
        return 0.0

def analyze_trades(trades: list) -> dict:
    """分析交易记录

    Args:
        trades: 交易记录列表

    Returns:
        dict: 交易统计指标
    """
    try:
        if not trades:
            return {}
        
        # 转换为DataFrame
        df = pd.DataFrame(trades)
        
        # 计算交易统计
        stats = {
            'total_trades': len(trades),
            'win_trades': len(df[df['pnl'] > 0]),
            'loss_trades': len(df[df['pnl'] <= 0]),
            'win_rate': len(df[df['pnl'] > 0]) / len(trades),
            'avg_profit': df[df['pnl'] > 0]['pnl'].mean() if len(df[df['pnl'] > 0]) > 0 else 0,
            'avg_loss': df[df['pnl'] <= 0]['pnl'].mean() if len(df[df['pnl'] <= 0]) > 0 else 0,
            'profit_factor': abs(df[df['pnl'] > 0]['pnl'].sum() / df[df['pnl'] <= 0]['pnl'].sum()) 
                              if len(df[df['pnl'] <= 0]) > 0 else float('inf'),
            'total_commission': df['commission'].sum(),
            'total_slippage': df['slippage'].sum()
        }
        
        return stats
    
    except Exception as e:
        logger.error(f"分析交易记录失败: {str(e)}")
        return {}