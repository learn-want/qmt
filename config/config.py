#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""配置管理模块

此模块负责：
1. 加载和解析配置文件
2. 提供配置参数的访问接口
3. 验证配置参数的有效性
"""

import os
import yaml
from typing import Dict, Any
from loguru import logger

def load_config(config_path: str) -> Dict[str, Any]:
    """加载配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        Dict[str, Any]: 配置参数字典

    Raises:
        FileNotFoundError: 配置文件不存在
        yaml.YAMLError: 配置文件格式错误
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 验证必要的配置项
        validate_config(config)
        
        # 设置默认值
        set_default_config(config)
        
        return config
    
    except yaml.YAMLError as e:
        logger.error(f"配置文件格式错误: {str(e)}")
        raise

def validate_config(config: Dict[str, Any]) -> None:
    """验证配置参数的有效性

    Args:
        config: 配置参数字典

    Raises:
        ValueError: 配置参数无效
    """
    required_fields = [
        'log_dir',           # 日志目录
        'data_dir',          # 数据目录
        'account',           # 账户配置
        'trading'            # 交易配置
    ]
    
    for field in required_fields:
        if field not in config:
            raise ValueError(f"缺少必要的配置项: {field}")

def set_default_config(config: Dict[str, Any]) -> None:
    """设置配置参数的默认值

    Args:
        config: 配置参数字典
    """
    defaults = {
        'log_level': 'INFO',
        'trading': {
            'order_timeout': 60,    # 订单超时时间（秒）
            'max_positions': 5,      # 最大持仓数
            'risk_limit': 0.1        # 风险限额（占总资金比例）
        },
        'backtest': {
            'start_date': '2023-01-01',
            'end_date': '2023-12-31',
            'initial_capital': 1000000
        }
    }
    
    for key, value in defaults.items():
        if key not in config:
            config[key] = value
        elif isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if sub_key not in config[key]:
                    config[key][sub_key] = sub_value