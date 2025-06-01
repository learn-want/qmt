#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""双均线交叉策略

此策略基于快速和慢速移动平均线的交叉来产生交易信号：
1. 当快线上穿慢线时，产生买入信号
2. 当快线下穿慢线时，产生卖出信号
3. 同时使用RSI指标进行辅助判断，过滤交易信号
"""

from typing import Dict, Any
import pandas as pd
from loguru import logger

from strategies.base_strategy import BaseStrategy
from utils.logger import strategy_log

class MACrossStrategy(BaseStrategy):
    """双均线交叉策略"""

    def initialize(self) -> None:
        """策略初始化"""
        # 获取策略参数
        self.ma_short = self.params.get('ma_short', 5)  # 短期均线周期
        self.ma_long = self.params.get('ma_long', 20)   # 长期均线周期
        self.rsi_period = self.params.get('rsi_period', 14)  # RSI周期
        self.rsi_buy = self.params.get('rsi_buy', 30)   # RSI买入阈值
        self.rsi_sell = self.params.get('rsi_sell', 70)  # RSI卖出阈值
        
        strategy_log(self.name, f"策略初始化 - 参数: MA短线={self.ma_short}, MA长线={self.ma_long}, "
                             f"RSI周期={self.rsi_period}, RSI买入={self.rsi_buy}, RSI卖出={self.rsi_sell}")

    def generate_signals(self, data: pd.DataFrame) -> Dict[str, float]:
        """生成交易信号

        Args:
            data: 市场数据

        Returns:
            Dict[str, float]: 交易信号字典，键为股票代码，值为仓位比例（-1到1）
        """
        try:
            signals = {}
            
            # 获取最新数据
            latest_data = data.iloc[-1]
            prev_data = data.iloc[-2] if len(data) > 1 else None
            
            if prev_data is None:
                return signals
            
            for code in self.universe:
                # 获取技术指标数据
                ma_short_prev = prev_data[f'ma_{self.ma_short}']
                ma_short_curr = latest_data[f'ma_{self.ma_short}']
                ma_long_prev = prev_data[f'ma_{self.ma_long}']
                ma_long_curr = latest_data[f'ma_{self.ma_long}']
                rsi_curr = latest_data['rsi']
                
                # 判断均线交叉
                cross_up = ma_short_prev < ma_long_prev and ma_short_curr > ma_long_curr
                cross_down = ma_short_prev > ma_long_prev and ma_short_curr < ma_long_curr
                
                # 生成交易信号
                signal = 0.0
                
                # 买入条件：均线金叉 且 RSI低于超卖线
                if cross_up and rsi_curr < self.rsi_buy:
                    signal = 1.0
                    strategy_log(self.name, f"买入信号 - {code}: 均线金叉, RSI={rsi_curr:.2f}")
                
                # 卖出条件：均线死叉 或 RSI高于超买线
                elif cross_down or rsi_curr > self.rsi_sell:
                    signal = -1.0
                    strategy_log(self.name, f"卖出信号 - {code}: {'均线死叉' if cross_down else 'RSI超买'}, "
                                         f"RSI={rsi_curr:.2f}")
                
                signals[code] = signal
            
            return signals
            
        except Exception as e:
            logger.error(f"信号生成错误 - {self.name}: {str(e)}")
            return {}

    def _calculate_position(self, code: str, signal: float) -> float:
        """计算目标仓位，重写父类方法

        Args:
            code: 股票代码
            signal: 交易信号

        Returns:
            float: 目标仓位
        """
        # 继承父类的仓位控制逻辑
        target_pos = super()._calculate_position(code, signal)
        
        # 添加自定义的仓位控制逻辑
        if target_pos > 0:
            # 买入时检查趋势强度
            trend_strength = self.data_processor.calculate_features(pd.DataFrame())['trend_strength'].iloc[-1]
            if trend_strength < 0.02:  # 趋势不明显时减少仓位
                target_pos *= 0.5
        
        return target_pos