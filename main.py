#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""主程序入口

此模块作为整个量化交易系统的入口点，负责：
1. 解析命令行参数
2. 加载配置文件
3. 初始化日志系统
4. 根据运行模式（回测/实盘）启动相应的引擎

使用示例：
    回测模式：python main.py --mode backtest --strategy example_strategy
    实盘模式：python main.py --mode live --strategy example_strategy
"""

import os
import sys
import click
from loguru import logger

from config.config import load_config
from utils.logger import setup_logger
from strategies.base_strategy import load_strategy
from backtest.backtest_engine import BacktestEngine
from trader.trading_engine import TradingEngine

@click.command()
@click.option('--mode', type=click.Choice(['backtest', 'live']), required=True, help='运行模式：回测或实盘')
@click.option('--strategy', required=True, help='策略名称')
@click.option('--config', default='config/settings.yaml', help='配置文件路径')
def main(mode: str, strategy: str, config: str):
    """主程序入口函数

    Args:
        mode: 运行模式，'backtest'或'live'
        strategy: 策略名称
        config: 配置文件路径
    """
    try:
        # 加载配置
        cfg = load_config(config)
        
        # 设置日志
        setup_logger(cfg['log_dir'], mode)
        logger.info(f"启动系统 - 模式: {mode}, 策略: {strategy}")
        
        # 加载策略
        strategy_class = load_strategy(strategy)
        strategy_instance = strategy_class(cfg)
        
        # 根据模式启动相应引擎
        if mode == 'backtest':
            engine = BacktestEngine(cfg)
            engine.run(strategy_instance)
        else:
            engine = TradingEngine(cfg)
            engine.run(strategy_instance)
            
    except Exception as e:
        logger.error(f"系统运行错误: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()