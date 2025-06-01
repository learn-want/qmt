#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""主程序入口

此模块作为整个量化交易系统的入口点，负责：
1. 解析命令行参数
2. 加载配置文件
3. 初始化日志系统
4. 根据运行模式（回测/实盘）启动相应的引擎

使用示例：
    通用策略：
        回测模式：python main.py --mode backtest --strategy example_strategy
        实盘模式：python main.py --mode live --strategy example_strategy
    
    首板打板策略：
        回测模式：python main.py --mode backtest --strategy first_board_strategy --config config/first_board_settings.yaml
        实盘模式：python main.py --mode live --strategy first_board_strategy --config config/first_board_settings.yaml
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
@click.option('--config', help='策略配置文件路径')
@click.option('--base_config', default='config/common_settings.yaml', help='基础配置文件路径')
@click.option('--start_date', help='回测开始日期，格式：YYYY-MM-DD')
@click.option('--end_date', help='回测结束日期，格式：YYYY-MM-DD')
@click.option('--initial_capital', type=float, help='初始资金')
def main(mode: str, strategy: str, config: str, base_config: str, start_date: str, end_date: str, initial_capital: float):
    """主程序入口函数

    Args:
        mode: 运行模式，'backtest'或'live'
        strategy: 策略名称
        config: 策略配置文件路径
        base_config: 基础配置文件路径
        start_date: 回测开始日期
        end_date: 回测结束日期
        initial_capital: 初始资金
    """
    try:
        # 如果未指定策略配置文件，则尝试使用策略名称对应的配置文件
        if not config:
            strategy_config = f"config/{strategy}_settings.yaml"
            if os.path.exists(strategy_config):
                config = strategy_config
                logger.info(f"使用策略配置文件: {config}")
            else:
                # 如果找不到策略特定配置，使用通用配置
                config = base_config
                logger.info(f"未找到策略特定配置，使用通用配置: {config}")
        
        # 加载配置（合并基础配置和策略配置）
        cfg = load_config(config, base_config if config != base_config else None)
        
        # 如果命令行参数提供了回测参数，则覆盖配置文件中的设置
        if mode == 'backtest':
            if start_date:
                cfg['backtest']['start_date'] = start_date
            if end_date:
                cfg['backtest']['end_date'] = end_date
            if initial_capital:
                cfg['backtest']['initial_capital'] = initial_capital
        
        # 设置日志
        setup_logger(cfg['log_dir'], mode)
        logger.info(f"启动系统 - 模式: {mode}, 策略: {strategy}")
        
        # 加载策略
        strategy_class = load_strategy(strategy)
        strategy_instance = strategy_class(cfg)
        
        # 根据模式启动相应引擎
        if mode == 'backtest':
            logger.info(f"回测期间: {cfg['backtest']['start_date']} 至 {cfg['backtest']['end_date']}")
            logger.info(f"初始资金: {cfg['backtest']['initial_capital']}")
            engine = BacktestEngine(cfg)
            engine.run(strategy_instance)
        else:
            logger.info("实盘交易模式启动")
            engine = TradingEngine(cfg)
            engine.run(strategy_instance)
            
    except Exception as e:
        logger.error(f"系统运行错误: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()