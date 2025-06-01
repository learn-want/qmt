# QMT量化交易系统

## 项目概述
本项目基于miniQMT平台开发的量化交易系统，实现自动化交易策略的研发、回测、优化和实盘部署。系统采用模块化设计，支持多市场、多品种的量化交易，并具备高性能、高可靠性和容错能力。

## 系统架构

### 1. 核心模块
- **数据模块** (`data/`)
  - 行情数据获取和处理
  - 历史数据管理和缓存
  - 实时数据订阅
  - 数据验证和错误处理

- **策略模块** (`strategies/`)
  - 策略基类
  - 具体策略实现
  - 信号生成
  - 策略参数优化

- **交易模块** (`trader/`)
  - 订单管理和状态跟踪
  - 仓位管理和资金控制
  - 风险控制和异常处理
  - 交易状态缓存和恢复

- **回测模块** (`backtest/`)
  - 历史数据回测
  - 性能评估和指标计算
  - 参数优化
  - 检查点保存和恢复

### 2. 辅助模块
- **配置模块** (`config/`)
  - 系统配置
  - 策略参数
  - 账户信息
  - 多级配置管理

- **日志模块** (`utils/logger.py`)
  - 运行日志
  - 交易记录
  - 错误追踪
  - 性能统计

- **工具模块** (`utils/`)
  - 数据处理工具
  - 指标计算
  - 性能分析
  - 缓存和重试机制

## 项目结构
```
qmt_trials/
├── data/                   # 数据模块
│   ├── data_fetcher.py     # 数据获取（含缓存和重试机制）
│   └── data_processor.py   # 数据处理（含缓存和性能优化）
├── strategies/             # 策略模块
│   ├── base_strategy.py    # 策略基类
│   ├── ma_cross_strategy.py # 均线交叉策略
│   ├── first_board_strategy.py # 首板打板策略
│   ├── README_ma_cross.md  # 均线交叉策略说明
│   └── README_first_board.md # 首板打板策略说明
├── trader/                 # 交易模块
│   └── trading_engine.py   # 交易引擎（含错误处理和状态恢复）
├── backtest/               # 回测模块
│   ├── backtest_engine.py  # 回测引擎（含检查点和缓存机制）
│   └── performance.py      # 性能评估
├── config/                 # 配置模块
│   ├── config.py           # 配置管理
│   ├── common_settings.yaml # 通用配置文件
│   ├── settings.yaml       # 默认配置文件
│   ├── ma_cross_settings.yaml # 均线交叉策略配置
│   └── first_board_settings.yaml # 首板打板策略配置
├── utils/                  # 工具模块
│   ├── logger.py           # 日志工具
│   └── indicators.py       # 技术指标
├── main.py                 # 主程序入口
└── README.md               # 项目文档
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
2. **默认配置**：`config/settings.yaml` - 包含默认配置参数
3. **策略配置**：`config/{strategy_name}_settings.yaml` - 包含策略特定的配置

配置加载规则：
- 如果指定了策略配置文件，系统会自动合并通用配置和策略配置
- 如果未指定配置文件，系统会自动查找与策略名称对应的配置文件
- 策略配置的优先级高于通用配置，会覆盖同名设置
- 支持命令行参数覆盖配置文件中的设置

配置内容包括：
- 数据源配置：数据接口、缓存设置、重试参数
- 交易配置：账户信息、交易规则、风控参数
- 回测配置：回测周期、滑点设置、手续费率
- 策略参数：指标参数、信号阈值、交易条件

## 已实现策略

### 1. 均线交叉策略 (MA Cross)
基于双均线交叉的经典趋势跟踪策略，结合RSI指标过滤信号。

### 2. 首板打板策略 (First Board)
A股市场特有的短线交易策略，针对首次涨停的个股进行操作，通过分析涨停强度、成交量、换手率等特征生成交易信号。详细说明请参考 [首板打板策略文档](strategies/README_first_board.md)。

## 错误处理与性能优化

### 错误处理机制
系统实现了多层次的错误处理机制，提高系统稳定性：

1. **异常类型定义**
   - `TradingError` - 交易相关异常
   - `BacktestError` - 回测相关异常
   - 自定义异常类型便于精确处理不同错误

2. **重试机制**
   - 装饰器实现的自动重试功能
   - 支持配置重试次数和间隔时间
   - 针对网络请求、数据获取等不稳定操作

3. **状态恢复**
   - 交易状态定期保存
   - 回测检查点机制
   - 异常发生时自动恢复

### 性能优化

1. **数据缓存**
   - 历史数据本地缓存
   - 计算结果缓存
   - 减少重复数据获取和计算

2. **批量处理**
   - 批量数据获取
   - 批量信号处理
   - 减少API调用次数

3. **性能监控**
   - 关键操作耗时统计
   - 性能瓶颈分析
   - 资源使用监控

## 开发规范
1. 代码风格遵循PEP 8规范
2. 所有模块、类和函数必须包含文档字符串
3. 使用类型注解提高代码可读性
4. 关键函数必须包含单元测试
5. 错误处理必须明确且全面

## 版本历史
- v0.2.0 - 性能与稳定性优化版本
  - 数据模块添加缓存和重试机制
  - 数据处理模块优化性能
  - 回测引擎添加检查点和恢复功能
  - 交易引擎增强错误处理和状态管理
  - 完善配置系统

- v0.1.0 - 初始版本
  - 基础项目结构搭建
  - 核心模块框架实现
  - 均线交叉和首板打板策略实现