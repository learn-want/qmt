#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""配置管理模块

此模块负责：
1. 加载和解析配置文件
2. 提供配置参数的访问接口
3. 验证配置参数的有效性
4. 合并通用配置和策略特定配置
"""

import os
import yaml
import copy
from typing import Dict, Any, Optional
from loguru import logger

def load_config(config_path: str, base_config_path: Optional[str] = None) -> Dict[str, Any]:
    """加载配置文件

    Args:
        config_path: 配置文件路径
        base_config_path: 基础配置文件路径，如果提供，将与策略配置合并

    Returns:
        Dict[str, Any]: 配置参数字典

    Raises:
        FileNotFoundError: 配置文件不存在
        yaml.YAMLError: 配置文件格式错误
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    try:
        # 加载策略配置
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 如果提供了基础配置路径，加载并合并配置
        if base_config_path and os.path.exists(base_config_path) and base_config_path != config_path:
            logger.info(f"合并基础配置: {base_config_path} 和策略配置: {config_path}")
            config = merge_configs(base_config_path, config)
        
        # 验证必要的配置项
        validate_config(config)
        
        # 设置默认值
        set_default_config(config)
        
        return config
    
    except yaml.YAMLError as e:
        logger.error(f"配置文件格式错误: {str(e)}")
        raise

def merge_configs(base_config_path: str, strategy_config: Dict[str, Any]) -> Dict[str, Any]:
    """合并基础配置和策略配置

    Args:
        base_config_path: 基础配置文件路径
        strategy_config: 策略配置字典

    Returns:
        Dict[str, Any]: 合并后的配置字典
    """
    try:
        # 加载基础配置
        with open(base_config_path, 'r', encoding='utf-8') as f:
            base_config = yaml.safe_load(f)
        
        # 创建基础配置的深拷贝
        merged_config = copy.deepcopy(base_config)
        
        # 递归合并配置
        deep_merge(merged_config, strategy_config)
        
        return merged_config
    
    except Exception as e:
        logger.error(f"合并配置失败: {str(e)}")
        # 如果合并失败，返回策略配置
        return strategy_config

def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    """递归合并两个字典

    Args:
        base: 基础字典，将被修改
        override: 覆盖字典，优先级更高
    """
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            # 如果两边都是字典，递归合并
            deep_merge(base[key], value)
        else:
            # 否则直接覆盖
            base[key] = value

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