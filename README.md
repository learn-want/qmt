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
│   ├── ma_cross_strategy.py # 均线交叉策略
│   ├── first_board_strategy.py # 首板打板策略
│   └── README_first_board.md # 首板打板策略说明
├── trader/                 # 交易模块
│   └── trading_engine.py   # 交易引擎
├── backtest/               # 回测模块
│   ├── backtest_engine.py  # 回测引擎
│   └── performance.py      # 性能评估
├── config/                 # 配置模块
│   ├── config.py          # 配置管理
│   ├── settings.yaml      # 通用配置文件
│   └── first_board_settings.yaml # 首板打板策略配置
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
# 通用策略回测
python main.py --mode backtest --strategy ma_cross_strategy

# 首板打板策略回测，使用特定配置文件
python main.py --mode backtest --strategy first_board_strategy --config config/first_board_settings.yaml --start_date 2023-01-01 --end_date 2023-12-31
```
3. 实盘交易：
```bash
# 通用策略实盘
python main.py --mode live --strategy ma_cross_strategy

# 首板打板策略实盘
python main.py --mode live --strategy first_board_strategy --config config/first_board_settings.yaml
```

## 配置系统
系统采用分层配置设计，支持通用配置和策略特定配置的分离：

1. **通用配置**：`config/common_settings.yaml` - 包含系统级别的通用配置
2. **策略配置**：`config/{strategy_name}_settings.yaml` - 包含策略特定的配置

配置加载规则：
- 如果指定了策略配置文件，系统会自动合并通用配置和策略配置
- 如果未指定配置文件，系统会自动查找与策略名称对应的配置文件
- 策略配置的优先级高于通用配置，会覆盖同名设置

## 已实现策略

### 1. 均线交叉策略 (MA Cross)
基于双均线交叉的经典趋势跟踪策略，结合RSI指标过滤信号。

### 2. 首板打板策略 (First Board)
A股市场特有的短线交易策略，针对首次涨停的个股进行操作，通过分析涨停强度、成交量、换手率等特征生成交易信号。详细说明请参考 [首板打板策略文档](strategies/README_first_board.md)。

## 开发规范
1. 代码风格遵循PEP 8规范
2. 所有模块、类和函数必须包含文档字符串
3. 使用类型注解提高代码可读性
4. 关键函数必须包含单元测试

## 版本历史
- v0.1.0 - 初始版本
  - 基础项目结构搭建
  - 核心模块框架实现