#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""回测引擎模块

此模块实现了策略回测功能，包括：
1. 历史数据回放
2. 模拟交易执行
3. 资金管理
4. 绩效评估
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List
from datetime import datetime
from loguru import logger

from strategies.base_strategy import BaseStrategy
from backtest.performance import (
    calculate_returns,
    calculate_drawdown,
    calculate_sharpe_ratio,
    calculate_alpha_beta
)

class BacktestEngine:
    """回测引擎类"""

    def __init__(self, config: Dict[str, Any]):
        """初始化回测引擎

        Args:
            config: 配置参数字典
        """
        self.config = config
        self.backtest_config = config['backtest']
        
        # 回测参数
        self.start_date = self.backtest_config['start_date']
        self.end_date = self.backtest_config['end_date']
        self.initial_capital = self.backtest_config['initial_capital']
        self.commission_rate = self.backtest_config['commission_rate']
        self.slippage = self.backtest_config['slippage']
        
        # 回测状态
        self.current_date = None
        self.positions = {}
        self.cash = self.initial_capital
        self.equity = self.initial_capital
        
        # 交易记录
        self.trades = []
        self.daily_returns = []
        
    def run(self, strategy: BaseStrategy) -> Dict[str, Any]:
        """运行回测

        Args:
            strategy: 策略实例

        Returns:
            Dict[str, Any]: 回测结果
        """
        try:
            logger.info(f"开始回测 - 策略: {strategy.name}, 周期: {self.start_date} 至 {self.end_date}")
            
            # 获取回测区间的交易日历
            trading_dates = strategy.data_fetcher.get_trading_dates(
                self.start_date,
                self.end_date
            )
            
            # 遍历每个交易日
            for date in trading_dates:
                self.current_date = date
                
                # 获取当日行情数据
                data = self._get_daily_data(strategy)
                if not data:
                    continue
                
                # 运行策略
                strategy.on_bar(data)
                
                # 更新回测状态
                self._update_backtest_status(data)
                
            # 计算回测绩效
            results = self._calculate_performance()
            
            logger.info(f"回测完成 - 策略: {strategy.name}")
            return results
            
        except Exception as e:
            logger.error(f"回测运行错误: {str(e)}")
            return {}
    
    def _get_daily_data(self, strategy: BaseStrategy) -> Dict[str, Any]:
        """获取当日市场数据

        Args:
            strategy: 策略实例

        Returns:
            Dict[str, Any]: 市场数据字典
        """
        try:
            data = {}
            for code in strategy.universe:
                # 获取历史数据
                hist_data = strategy.data_fetcher.get_history_data(
                    code=code,
                    period='1d',
                    count=strategy.config['data']['history_length']
                )
                if hist_data:
                    data[code] = hist_data[code]
            return data
        
        except Exception as e:
            logger.error(f"获取回测数据失败: {str(e)}")
            return {}
    
    def _update_backtest_status(self, data: Dict[str, Any]) -> None:
        """更新回测状态

        Args:
            data: 市场数据字典
        """
        try:
            # 更新持仓市值
            portfolio_value = self.cash
            for code, pos in self.positions.items():
                if code in data:
                    close_price = data[code]['close'][-1]
                    market_value = pos * close_price
                    portfolio_value += market_value
            
            # 计算日收益率
            daily_return = (portfolio_value - self.equity) / self.equity
            self.daily_returns.append({
                'date': self.current_date,
                'return': daily_return
            })
            
            # 更新权益
            self.equity = portfolio_value
            
        except Exception as e:
            logger.error(f"更新回测状态失败: {str(e)}")
    
    def _calculate_performance(self) -> Dict[str, Any]:
        """计算回测绩效

        Returns:
            Dict[str, Any]: 绩效指标字典
        """
        try:
            # 转换日收益率为DataFrame
            returns_df = pd.DataFrame(self.daily_returns)
            returns_df.set_index('date', inplace=True)
            
            # 计算累计收益
            total_return = calculate_returns(returns_df['return'])
            
            # 计算最大回撤
            max_drawdown = calculate_drawdown(returns_df['return'])
            
            # 计算夏普比率
            sharpe_ratio = calculate_sharpe_ratio(returns_df['return'])
            
            # 计算Alpha和Beta
            alpha, beta = calculate_alpha_beta(returns_df['return'])
            
            # 汇总结果
            results = {
                'total_return': total_return,
                'annual_return': total_return / len(returns_df) * 252,
                'max_drawdown': max_drawdown,
                'sharpe_ratio': sharpe_ratio,
                'alpha': alpha,
                'beta': beta,
                'trade_count': len(self.trades),
                'win_rate': sum(t['pnl'] > 0 for t in self.trades) / len(self.trades) if self.trades else 0,
                'daily_returns': returns_df.to_dict(),
                'trades': self.trades
            }
            
            return results
            
        except Exception as e:
            logger.error(f"计算回测绩效失败: {str(e)}")
            return {}
    
    def place_order(self, code: str, direction: str, volume: float, price: float) -> bool:
        """模拟下单

        Args:
            code: 股票代码
            direction: 交易方向，'buy'或'sell'
            volume: 交易数量
            price: 交易价格

        Returns:
            bool: 下单是否成功
        """
        try:
            # 计算交易成本
            commission = price * volume * self.commission_rate
            slippage_cost = price * volume * self.slippage
            total_cost = price * volume + commission + slippage_cost
            
            if direction == 'buy':
                # 检查资金是否足够
                if total_cost > self.cash:
                    logger.warning(f"资金不足 - 所需: {total_cost:.2f}, 现有: {self.cash:.2f}")
                    return False
                
                # 更新持仓和资金
                self.positions[code] = self.positions.get(code, 0) + volume
                self.cash -= total_cost
                
            else:  # sell
                # 检查持仓是否足够
                if code not in self.positions or self.positions[code] < volume:
                    logger.warning(f"持仓不足 - 代码: {code}, 所需: {volume}, 现有: {self.positions.get(code, 0)}")
                    return False
                
                # 更新持仓和资金
                self.positions[code] -= volume
                if self.positions[code] == 0:
                    del self.positions[code]
                self.cash += total_cost
            
            # 记录交易
            self.trades.append({
                'date': self.current_date,
                'code': code,
                'direction': direction,
                'volume': volume,
                'price': price,
                'commission': commission,
                'slippage': slippage_cost,
                'pnl': -commission - slippage_cost  # 初始化交易盈亏
            })
            
            return True
            
        except Exception as e:
            logger.error(f"模拟下单失败: {str(e)}")
            return False