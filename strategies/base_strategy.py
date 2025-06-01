#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""策略基类模块

此模块定义了策略开发的基本框架，包括：
1. 策略初始化
2. 数据处理
3. 信号生成
4. 交易执行
5. 风险控制
"""

import os
import importlib
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime

import pandas as pd
from loguru import logger

from data.data_fetcher import DataFetcher
from data.data_processor import DataProcessor
from utils.logger import strategy_log

class BaseStrategy(ABC):
    """策略基类"""

    def __init__(self, config: Dict[str, Any]):
        """初始化策略

        Args:
            config: 配置参数字典
        """
        self.config = config
        self.name = self.__class__.__name__
        
        # 初始化数据模块
        self.data_fetcher = DataFetcher(config)
        self.data_processor = DataProcessor(config)
        
        # 策略参数
        self.universe = config['data']['universe']
        self.params = config.get('strategy_params', {})
        
        # 交易状态
        self.positions = {}
        self.orders = {}
        
        # 初始化策略
        self.initialize()
        
    def initialize(self) -> None:
        """策略初始化，可在子类中重写"""
        pass
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> Dict[str, float]:
        """生成交易信号

        Args:
            data: 市场数据

        Returns:
            Dict[str, float]: 交易信号字典，键为股票代码，值为仓位比例（-1到1）
        """
        raise NotImplementedError("必须实现generate_signals方法")
    
    def on_bar(self, data: Dict[str, Any]) -> None:
        """K线数据更新事件

        Args:
            data: K线数据字典
        """
        try:
            # 处理数据
            df = self.data_processor.process_kline_data(data)
            if df.empty:
                return
            
            # 生成信号
            signals = self.generate_signals(df)
            
            # 执行交易
            self.execute_trades(signals)
            
        except Exception as e:
            logger.error(f"策略运行错误 - {self.name}: {str(e)}")
    
    def execute_trades(self, signals: Dict[str, float]) -> None:
        """执行交易

        Args:
            signals: 交易信号字典
        """
        try:
            for code, signal in signals.items():
                # 检查是否可交易
                if not self._check_tradable(code):
                    continue
                
                # 获取当前持仓
                current_pos = self.positions.get(code, 0)
                
                # 计算目标仓位
                target_pos = self._calculate_position(code, signal)
                
                # 生成交易指令
                if target_pos > current_pos:
                    self._buy(code, target_pos - current_pos)
                elif target_pos < current_pos:
                    self._sell(code, current_pos - target_pos)
                    
        except Exception as e:
            logger.error(f"交易执行错误 - {self.name}: {str(e)}")
    
    def _check_tradable(self, code: str) -> bool:
        """检查股票是否可交易

        Args:
            code: 股票代码

        Returns:
            bool: 是否可交易
        """
        # 检查交易时间
        if not self.data_fetcher.is_trading_time():
            return False
        
        # 检查是否停牌
        stock_info = self.data_fetcher.get_stock_info(code)
        if not stock_info:
            return False
        
        return True
    
    def _calculate_position(self, code: str, signal: float) -> float:
        """计算目标仓位

        Args:
            code: 股票代码
            signal: 交易信号

        Returns:
            float: 目标仓位
        """
        # 获取风险限额
        risk_limit = self.config['trading']['risk_limit']
        
        # 根据信号强度计算目标仓位
        target_pos = signal * risk_limit
        
        # 确保不超过最大持仓限制
        max_positions = self.config['trading']['max_positions']
        if len(self.positions) >= max_positions and code not in self.positions:
            return 0
        
        return target_pos
    
    def _buy(self, code: str, amount: float) -> None:
        """买入操作

        Args:
            code: 股票代码
            amount: 买入数量
        """
        strategy_log(self.name, f"买入信号 - 代码: {code}, 数量: {amount}")
        # 具体交易操作由交易模块实现
    
    def _sell(self, code: str, amount: float) -> None:
        """卖出操作

        Args:
            code: 股票代码
            amount: 卖出数量
        """
        strategy_log(self.name, f"卖出信号 - 代码: {code}, 数量: {amount}")
        # 具体交易操作由交易模块实现

def load_strategy(strategy_name: str) -> type:
    """加载策略类

    Args:
        strategy_name: 策略名称

    Returns:
        type: 策略类

    Raises:
        ImportError: 策略模块导入失败
        AttributeError: 策略类不存在
    """
    try:
        # 导入策略模块
        module = importlib.import_module(f"strategies.{strategy_name}")
        
        # 获取策略类（假设类名与文件名相同）
        strategy_class = getattr(module, strategy_name)
        
        # 验证是否为BaseStrategy的子类
        if not issubclass(strategy_class, BaseStrategy):
            raise TypeError(f"{strategy_name}不是BaseStrategy的子类")
        
        return strategy_class
    
    except ImportError as e:
        logger.error(f"策略模块导入失败: {str(e)}")
        raise
    except AttributeError as e:
        logger.error(f"策略类不存在: {str(e)}")
        raise