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
import os
import pickle
import time
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime
from functools import wraps
from loguru import logger

from strategies.base_strategy import BaseStrategy
from backtest.performance import (
    calculate_returns,
    calculate_drawdown,
    calculate_sharpe_ratio,
    calculate_alpha_beta
)

# 定义回测异常类
class BacktestError(Exception):
    """回测过程中的异常"""
    pass

# 定义重试装饰器
def retry_on_error(max_attempts: int = 3, delay: float = 1.0):
    """函数执行失败时进行重试的装饰器
    
    Args:
        max_attempts: 最大重试次数
        delay: 重试间隔时间(秒)
        
    Returns:
        装饰后的函数
    """
    def decorator(func):
        @wraps(func)
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
                    logger.warning(f"函数 {func.__name__} 执行失败，正在进行第 {attempts} 次重试: {str(e)}")
                    time.sleep(delay)
        return wrapper
    return decorator

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
        self.last_checkpoint_date = None
        
        # 交易记录
        self.trades = []
        self.daily_returns = []
        
        # 性能优化
        self.data_cache = {}
        self.checkpoint_interval = self.backtest_config.get('checkpoint_interval', 20)  # 默认每20个交易日保存一次检查点
        
        # 创建缓存目录
        self.cache_dir = os.path.join(os.getcwd(), 'backtest', 'cache')
        self.checkpoint_dir = os.path.join(os.getcwd(), 'backtest', 'checkpoints')
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        
        # 初始化统计信息
        self.stats = {
            'execution_time': 0,
            'data_fetch_time': 0,
            'signal_generation_time': 0,
            'order_execution_time': 0
        }
        
    def get_checkpoint_path(self, strategy_name: str) -> str:
        """获取检查点文件路径
        
        Args:
            strategy_name: 策略名称
            
        Returns:
            str: 检查点文件路径
        """
        return os.path.join(self.checkpoint_dir, f"{strategy_name}_{self.start_date}_{self.end_date}.pkl")
    
    def save_checkpoint(self, strategy_name: str) -> bool:
        """保存回测检查点
        
        Args:
            strategy_name: 策略名称
            
        Returns:
            bool: 是否保存成功
        """
        try:
            checkpoint = {
                'current_date': self.current_date,
                'positions': self.positions.copy(),
                'cash': self.cash,
                'equity': self.equity,
                'trades': self.trades.copy(),
                'daily_returns': self.daily_returns.copy(),
                'stats': self.stats.copy()
            }
            
            checkpoint_path = self.get_checkpoint_path(strategy_name)
            with open(checkpoint_path, 'wb') as f:
                pickle.dump(checkpoint, f)
                
            self.last_checkpoint_date = self.current_date
            logger.debug(f"保存回测检查点 - 日期: {self.current_date}, 策略: {strategy_name}")
            return True
            
        except Exception as e:
            logger.error(f"保存回测检查点失败: {str(e)}")
            return False
    
    def load_checkpoint(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """加载回测检查点
        
        Args:
            strategy_name: 策略名称
            
        Returns:
            Optional[Dict[str, Any]]: 检查点数据，如果不存在则返回None
        """
        try:
            checkpoint_path = self.get_checkpoint_path(strategy_name)
            if not os.path.exists(checkpoint_path):
                return None
                
            with open(checkpoint_path, 'rb') as f:
                checkpoint = pickle.load(f)
                
            logger.info(f"加载回测检查点 - 日期: {checkpoint['current_date']}, 策略: {strategy_name}")
            return checkpoint
            
        except Exception as e:
            logger.error(f"加载回测检查点失败: {str(e)}")
            return None
    
    def restore_from_checkpoint(self, checkpoint: Dict[str, Any]) -> None:
        """从检查点恢复回测状态
        
        Args:
            checkpoint: 检查点数据
        """
        try:
            self.current_date = checkpoint['current_date']
            self.positions = checkpoint['positions']
            self.cash = checkpoint['cash']
            self.equity = checkpoint['equity']
            self.trades = checkpoint['trades']
            self.daily_returns = checkpoint['daily_returns']
            self.stats = checkpoint.get('stats', self.stats)
            self.last_checkpoint_date = self.current_date
            
            logger.info(f"恢复回测状态 - 日期: {self.current_date}")
            
        except Exception as e:
            logger.error(f"恢复回测状态失败: {str(e)}")
            raise BacktestError(f"恢复回测状态失败: {str(e)}")
    
    @retry_on_error(max_attempts=3, delay=1.0)
    def run(self, strategy: BaseStrategy) -> Dict[str, Any]:
        """运行回测

        Args:
            strategy: 策略实例

        Returns:
            Dict[str, Any]: 回测结果
        """
        start_time = time.time()
        try:
            logger.info(f"开始回测 - 策略: {strategy.name}, 周期: {self.start_date} 至 {self.end_date}")
            
            # 尝试加载检查点
            checkpoint = self.load_checkpoint(strategy.name)
            if checkpoint:
                self.restore_from_checkpoint(checkpoint)
                logger.info(f"从检查点恢复回测 - 日期: {self.current_date}")
            
            # 获取回测区间的交易日历
            trading_dates = strategy.data_fetcher.get_trading_dates(
                self.start_date,
                self.end_date
            )
            
            # 确定起始索引
            start_idx = 0
            if checkpoint and self.current_date in trading_dates:
                start_idx = trading_dates.index(self.current_date) + 1
                if start_idx >= len(trading_dates):
                    logger.info("检查点已是最后一个交易日，回测已完成")
                    return self._calculate_performance()
            
            # 遍历每个交易日
            for i, date in enumerate(trading_dates[start_idx:], start_idx):
                self.current_date = date
                logger.debug(f"回测日期: {date} ({i+1}/{len(trading_dates)})")
                
                try:
                    # 获取当日行情数据
                    data_fetch_start = time.time()
                    data = self._get_daily_data(strategy)
                    self.stats['data_fetch_time'] += time.time() - data_fetch_start
                    
                    if not data:
                        logger.warning(f"日期 {date} 没有行情数据，跳过")
                        continue
                    
                    # 运行策略
                    signal_start = time.time()
                    strategy.on_bar(data)
                    self.stats['signal_generation_time'] += time.time() - signal_start
                    
                    # 更新回测状态
                    self._update_backtest_status(data)
                    
                    # 定期保存检查点
                    if (i + 1) % self.checkpoint_interval == 0 or i == len(trading_dates) - 1:
                        self.save_checkpoint(strategy.name)
                        
                except Exception as e:
                    logger.error(f"回测日期 {date} 处理失败: {str(e)}")
                    # 如果有检查点，可以从上一个检查点恢复
                    if self.last_checkpoint_date:
                        logger.warning(f"尝试从上一个检查点恢复: {self.last_checkpoint_date}")
                        checkpoint = self.load_checkpoint(strategy.name)
                        if checkpoint:
                            self.restore_from_checkpoint(checkpoint)
                            continue
                    raise
                
            # 计算回测绩效
            results = self._calculate_performance()
            
            # 记录执行时间
            self.stats['execution_time'] = time.time() - start_time
            results['stats'] = self.stats
            
            logger.info(f"回测完成 - 策略: {strategy.name}, 耗时: {self.stats['execution_time']:.2f}秒")
            return results
            
        except Exception as e:
            logger.error(f"回测运行错误: {str(e)}")
            # 尝试保存当前状态作为检查点
            if self.current_date:
                self.save_checkpoint(f"{strategy.name}_error")
            return {'error': str(e)}
    
    def _get_cache_key(self, code: str, date: str, history_length: int) -> str:
        """生成数据缓存键
        
        Args:
            code: 股票代码
            date: 日期
            history_length: 历史数据长度
            
        Returns:
            str: 缓存键
        """
        return f"{code}_{date}_{history_length}"
    
    def _cache_daily_data(self, code: str, date: str, history_length: int, data: Dict[str, Any]) -> None:
        """缓存每日数据
        
        Args:
            code: 股票代码
            date: 日期
            history_length: 历史数据长度
            data: 数据字典
        """
        try:
            cache_key = self._get_cache_key(code, date, history_length)
            cache_path = os.path.join(self.cache_dir, f"{cache_key}.pkl")
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            logger.warning(f"缓存数据失败 - 代码: {code}, 日期: {date}, 错误: {str(e)}")
    
    def _get_cached_data(self, code: str, date: str, history_length: int) -> Optional[Dict[str, Any]]:
        """获取缓存的数据
        
        Args:
            code: 股票代码
            date: 日期
            history_length: 历史数据长度
            
        Returns:
            Optional[Dict[str, Any]]: 缓存的数据，如果不存在则返回None
        """
        try:
            cache_key = self._get_cache_key(code, date, history_length)
            cache_path = os.path.join(self.cache_dir, f"{cache_key}.pkl")
            if os.path.exists(cache_path):
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
        except Exception as e:
            logger.warning(f"读取缓存数据失败 - 代码: {code}, 日期: {date}, 错误: {str(e)}")
        return None
    
    @retry_on_error(max_attempts=2, delay=0.5)
    def _get_daily_data(self, strategy: BaseStrategy) -> Dict[str, Any]:
        """获取当日市场数据

        Args:
            strategy: 策略实例

        Returns:
            Dict[str, Any]: 市场数据字典
        """
        try:
            data = {}
            history_length = strategy.config['data']['history_length']
            
            # 检查数据缓存
            for code in strategy.universe:
                cached_data = self._get_cached_data(code, self.current_date, history_length)
                if cached_data:
                    data[code] = cached_data[code]
            
            # 获取未缓存的数据
            missing_codes = [code for code in strategy.universe if code not in data]
            if missing_codes:
                logger.debug(f"获取未缓存数据 - 代码数量: {len(missing_codes)}, 日期: {self.current_date}")
                
                # 尝试批量获取数据
                try:
                    batch_data = strategy.data_fetcher.get_batch_history_data(
                        codes=missing_codes,
                        period='1d',
                        count=history_length
                    )
                    
                    # 处理批量数据
                    for code in missing_codes:
                        if code in batch_data:
                            data[code] = batch_data[code]
                            # 缓存数据
                            self._cache_daily_data(code, self.current_date, history_length, {code: batch_data[code]})
                        else:
                            logger.warning(f"批量获取数据失败 - 代码: {code}, 日期: {self.current_date}")
                            
                except Exception as e:
                    logger.error(f"批量获取数据失败: {str(e)}，将回退到单个获取")
                    
                    # 回退到单个获取
                    for code in missing_codes:
                        if code in data:  # 已经在批量获取中成功获取
                            continue
                            
                        try:
                            hist_data = strategy.data_fetcher.get_history_data(
                                code=code,
                                period='1d',
                                count=history_length
                            )
                            if hist_data and code in hist_data:
                                data[code] = hist_data[code]
                                # 缓存数据
                                self._cache_daily_data(code, self.current_date, history_length, {code: hist_data[code]})
                        except Exception as code_e:
                            logger.error(f"获取单个数据失败 - 代码: {code}, 错误: {str(code_e)}")
            
            # 验证数据完整性
            for code in list(data.keys()):
                if not strategy.data_fetcher.validate_data(data, code):
                    logger.warning(f"数据验证失败，移除无效数据 - 代码: {code}")
                    del data[code]
            
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