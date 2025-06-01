#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""日志工具模块

此模块负责：
1. 配置日志系统
2. 提供统一的日志记录接口
3. 实现日志的分类存储和格式化输出
"""

import os
import sys
from typing import Optional
from datetime import datetime
from loguru import logger

def setup_logger(log_dir: str, mode: str, level: Optional[str] = "INFO") -> None:
    """配置日志系统

    Args:
        log_dir: 日志存储目录
        mode: 运行模式（'backtest'或'live'）
        level: 日志级别，默认为'INFO'

    Note:
        日志文件按照以下规则存储：
        - {log_dir}/{mode}/{date}/system.log - 系统运行日志
        - {log_dir}/{mode}/{date}/trade.log - 交易相关日志
        - {log_dir}/{mode}/{date}/error.log - 错误日志
    """
    # 创建日志目录
    date_str = datetime.now().strftime("%Y%m%d")
    log_path = os.path.join(log_dir, mode, date_str)
    os.makedirs(log_path, exist_ok=True)

    # 清除默认处理器
    logger.remove()

    # 添加控制台输出
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        level=level,
        enqueue=True
    )

    # 系统日志
    logger.add(
        os.path.join(log_path, "system.log"),
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
        level=level,
        rotation="00:00",  # 每天轮换
        retention="30 days",  # 保留30天
        enqueue=True
    )

    # 交易日志
    logger.add(
        os.path.join(log_path, "trade.log"),
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {message}",
        filter=lambda record: "trade" in record["extra"],
        rotation="00:00",
        retention="30 days",
        enqueue=True
    )

    # 错误日志
    logger.add(
        os.path.join(log_path, "error.log"),
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
               "{name}:{function}:{line} | {message}",
        level="ERROR",
        rotation="00:00",
        retention="30 days",
        enqueue=True
    )

def trade_log(message: str) -> None:
    """记录交易相关日志

    Args:
        message: 日志消息
    """
    logger.bind(trade=True).info(message)

def strategy_log(strategy_name: str, message: str) -> None:
    """记录策略相关日志

    Args:
        strategy_name: 策略名称
        message: 日志消息
    """
    logger.bind(strategy=strategy_name).info(message)