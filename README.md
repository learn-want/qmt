# QMT量化交易系统

## 项目概述
本项目基于miniQMT平台开发的量化交易系统，实现自动化交易策略的研发、回测、优化和实盘部署。系统采用模块化设计，支持多市场、多品种的量化交易。

## 系统架构

### 1. 核心模块
- **数据模块** (`data/`)
  - 行情数据获取和处理
  - 历史数据管理
  - 实时数据订阅

- **策略模块** (`strategies/`)
  - 策略基类
  - 具体策略实现
  - 信号生成

- **交易模块** (`trader/`)
  - 订单管理
  - 仓位管理
  - 风险控制

- **回测模块** (`backtest/`)
  - 历史数据回测
  - 性能评估
  - 参数优化

### 2. 辅助模块
- **配置模块** (`config/`)
  - 系统配置
  - 策略参数
  - 账户信息

- **日志模块** (`utils/logger.py`)
  - 运行日志
  - 交易记录
  - 错误追踪

- **工具模块** (`utils/`)
  - 数据处理工具
  - 指标计算
  - 性能分析

## 项目结构
```
qmt_trials/
├── data/                   # 数据模块
│   ├── data_fetcher.py     # 数据获取
│   └── data_processor.py   # 数据处理
├── strategies/             # 策略模块
│   ├── base_strategy.py    # 策略基类
│   └── example_strategy.py # 示例策略
├── trader/                 # 交易模块
│   ├── order_manager.py    # 订单管理
│   └── position_manager.py # 仓位管理
├── backtest/               # 回测模块
│   ├── backtest_engine.py  # 回测引擎
│   └── performance.py      # 性能评估
├── config/                 # 配置模块
│   ├── config.py          # 配置管理
│   └── settings.yaml      # 配置文件
├── utils/                  # 工具模块
│   ├── logger.py          # 日志工具
│   └── indicators.py      # 技术指标
├── main.py                # 主程序入口
└── README.md              # 项目文档
```

## 环境要求
- Python 3.6-3.11 (64位)
- miniQMT平台
- xtquant库

## 安装说明
1. 安装miniQMT平台
2. 安装Python依赖：
```bash
pip install -r requirements.txt
```

## 使用说明
1. 配置账户信息和策略参数
2. 运行回测：
```bash
python main.py --mode backtest --strategy example_strategy
```
3. 实盘交易：
```bash
python main.py --mode live --strategy example_strategy
```

## 开发规范
1. 代码风格遵循PEP 8规范
2. 所有模块、类和函数必须包含文档字符串
3. 使用类型注解提高代码可读性
4. 关键函数必须包含单元测试

## 版本历史
- v0.1.0 - 初始版本
  - 基础项目结构搭建
  - 核心模块框架实现