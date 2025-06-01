#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""交易引擎模块

此模块实现了实盘交易的核心功能，包括：
1. 订单管理
2. 仓位管理
3. 风险控制
4. 交易执行
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger

from xtquant.xttype import StockAccount
from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback

from strategies.base_strategy import BaseStrategy
from utils.logger import trade_log

class TradingCallback(XtQuantTraderCallback):
    """交易回调类"""

    def __init__(self):
        super().__init__()

    def on_disconnected(self):
        """连接断开回调"""
        logger.error("交易连接断开")

    def on_stock_order(self, order):
        """委托回报推送

        Args:
            order: XtOrder对象
        """
        trade_log(f"委托回报 - 代码: {order.stock_code}, 状态: {order.order_status}, "
                 f"委托编号: {order.order_sysid}")

    def on_stock_trade(self, trade):
        """成交回报推送

        Args:
            trade: XtTrade对象
        """
        trade_log(f"成交回报 - 账户: {trade.account_id}, 代码: {trade.stock_code}, "
                 f"委托编号: {trade.order_id}")

    def on_order_error(self, order_error):
        """委托失败推送

        Args:
            order_error: XtOrderError对象
        """
        logger.error(f"委托失败 - 委托编号: {order_error.order_id}, "
                    f"错误码: {order_error.error_id}, 错误信息: {order_error.error_msg}")

    def on_cancel_error(self, cancel_error):
        """撤单失败推送

        Args:
            cancel_error: XtCancelError对象
        """
        logger.error(f"撤单失败 - 委托编号: {cancel_error.order_id}, "
                    f"错误码: {cancel_error.error_id}, 错误信息: {cancel_error.error_msg}")

class TradingEngine:
    """交易引擎类"""

    def __init__(self, config: Dict[str, Any]):
        """初始化交易引擎

        Args:
            config: 配置参数字典
        """
        self.config = config
        self.account_config = config['account']
        
        # 初始化交易接口
        self.trader = XtQuantTrader(TradingCallback())
        self.account = StockAccount(self.account_config['account_id'])
        
        # 交易状态
        self.orders = {}
        self.positions = {}
        
        # 初始化交易接口
        self._init_trader()
    
    def _init_trader(self) -> None:
        """初始化交易接口"""
        try:
            # 创建交易连接
            self.trader.start()
            
            # 订阅交易推送
            self.trader.subscribe(self.account)
            
            logger.info(f"交易接口初始化成功 - 账户: {self.account.account_id}")
            
        except Exception as e:
            logger.error(f"交易接口初始化失败: {str(e)}")
            raise
    
    def run(self, strategy: BaseStrategy) -> None:
        """运行交易引擎

        Args:
            strategy: 策略实例
        """
        try:
            logger.info(f"启动交易引擎 - 策略: {strategy.name}")
            
            # 更新账户信息
            self._update_account_info()
            
            # 运行策略
            while True:
                # 检查是否为交易时段
                if not strategy.data_fetcher.is_trading_time():
                    continue
                
                # 获取市场数据
                data = self._get_market_data(strategy)
                if not data:
                    continue
                
                # 运行策略
                strategy.on_bar(data)
                
                # 更新交易状态
                self._update_trading_status()
                
        except Exception as e:
            logger.error(f"交易引擎运行错误: {str(e)}")
            raise
        
        finally:
            self.trader.stop()
    
    def _get_market_data(self, strategy: BaseStrategy) -> Dict[str, Any]:
        """获取市场数据

        Args:
            strategy: 策略实例

        Returns:
            Dict[str, Any]: 市场数据字典
        """
        try:
            data = {}
            for code in strategy.universe:
                # 获取实时数据
                market_data = strategy.data_fetcher.get_realtime_data(code)
                if market_data:
                    data[code] = market_data
            return data
            
        except Exception as e:
            logger.error(f"获取市场数据失败: {str(e)}")
            return {}
    
    def _update_account_info(self) -> None:
        """更新账户信息"""
        try:
            # 查询资金信息
            assets = self.trader.query_stock_assets(self.account)
            if assets:
                trade_log(f"账户资金 - 总资产: {assets.total_asset:.2f}, "
                         f"可用资金: {assets.cash:.2f}")
            
            # 查询持仓信息
            positions = self.trader.query_stock_positions(self.account)
            if positions:
                for pos in positions:
                    self.positions[pos.stock_code] = pos.volume
                    trade_log(f"账户持仓 - 代码: {pos.stock_code}, "
                             f"数量: {pos.volume}, 可用: {pos.can_use_volume}")
                    
        except Exception as e:
            logger.error(f"更新账户信息失败: {str(e)}")
    
    def _update_trading_status(self) -> None:
        """更新交易状态"""
        try:
            # 查询未完成订单
            orders = self.trader.query_stock_orders(self.account, False)
            if orders:
                for order in orders:
                    if order.order_status not in ['已成交', '已撤单', '已拒绝']:
                        # 检查订单超时
                        order_time = datetime.strptime(order.order_time, '%H:%M:%S')
                        if (datetime.now() - order_time).seconds > self.config['trading']['order_timeout']:
                            # 撤销超时订单
                            self.trader.cancel_order_stock(self.account, order.order_id)
                            trade_log(f"撤销超时订单 - 委托号: {order.order_id}")
                    
        except Exception as e:
            logger.error(f"更新交易状态失败: {str(e)}")
    
    def place_order(self, code: str, direction: str, volume: float, price: float) -> bool:
        """下单

        Args:
            code: 股票代码
            direction: 交易方向，'buy'或'sell'
            volume: 交易数量
            price: 交易价格

        Returns:
            bool: 下单是否成功
        """
        try:
            # 检查是否可交易
            if not self._check_tradable(code, direction, volume):
                return False
            
            # 执行下单
            if direction == 'buy':
                order_id = self.trader.order_stock(self.account, code, price, volume, 'buy')
            else:
                order_id = self.trader.order_stock(self.account, code, price, volume, 'sell')
            
            if order_id:
                trade_log(f"下单成功 - 代码: {code}, 方向: {direction}, "
                         f"数量: {volume}, 价格: {price}, 委托号: {order_id}")
                return True
            else:
                logger.error(f"下单失败 - 代码: {code}, 方向: {direction}")
                return False
            
        except Exception as e:
            logger.error(f"下单执行错误: {str(e)}")
            return False
    
    def _check_tradable(self, code: str, direction: str, volume: float) -> bool:
        """检查是否可交易

        Args:
            code: 股票代码
            direction: 交易方向
            volume: 交易数量

        Returns:
            bool: 是否可交易
        """
        try:
            # 检查交易时间
            if not self.data_fetcher.is_trading_time():
                logger.warning("非交易时段")
                return False
            
            # 检查持仓限制
            if direction == 'buy':
                if len(self.positions) >= self.config['trading']['max_positions'] \
                        and code not in self.positions:
                    logger.warning(f"超过最大持仓限制: {self.config['trading']['max_positions']}")
                    return False
            else:
                if code not in self.positions or self.positions[code] < volume:
                    logger.warning(f"持仓不足 - 代码: {code}, 所需: {volume}, "
                                 f"现有: {self.positions.get(code, 0)}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"交易检查失败: {str(e)}")
            return False