#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""交易引擎模块

此模块实现了实盘交易的核心功能，包括：
1. 订单管理
2. 仓位管理
3. 风险控制
4. 交易执行
"""

import time
import os
import pickle
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime, timedelta
from functools import wraps
from loguru import logger

from xtquant.xttype import StockAccount
from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback

from strategies.base_strategy import BaseStrategy
from utils.logger import trade_log

# 定义交易异常类
class TradingError(Exception):
    """交易过程中的异常"""
    pass

# 定义重试装饰器
def retry_on_error(max_attempts: int = 3, delay: float = 1.0):
    """函数执行失败时进行重试的装饰器
    
    Args:
        max_attempts: 最大重试次数
        delay: 重试间隔时间(秒)
        
    Returns:
        装饰后的函数
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts == max_attempts:
                        logger.error(f"函数 {func.__name__} 执行失败，已重试 {attempts} 次: {str(e)}")
                        raise
                    logger.warning(f"函数 {func.__name__} 执行失败，正在进行第 {attempts} 次重试: {str(e)}")
                    time.sleep(delay)
        return wrapper
    return decorator

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
        self.trading_config = config['trading']
        
        # 初始化交易接口
        self.callback = TradingCallback()
        self.trader = XtQuantTrader(self.callback)
        self.account = StockAccount(self.account_config['account_id'])
        
        # 交易状态
        self.orders = {}
        self.positions = {}
        self.assets = None
        self.connected = False
        self.last_update_time = None
        
        # 创建缓存目录
        self.cache_dir = os.path.join(os.getcwd(), 'trader', 'cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # 性能统计
        self.stats = {
            'order_count': 0,
            'success_count': 0,
            'fail_count': 0,
            'connection_errors': 0,
            'reconnect_count': 0
        }
        
        # 初始化交易接口
        self._init_trader()
    
    @retry_on_error(max_attempts=3, delay=2.0)
    def _init_trader(self) -> None:
        """初始化交易接口"""
        try:
            # 创建交易连接
            if not self.trader.start():
                raise TradingError("交易接口启动失败")
            
            # 等待连接建立
            retry_count = 0
            max_retries = 5
            while retry_count < max_retries:
                if self.trader.is_connected():
                    break
                logger.info(f"等待交易连接建立，尝试 {retry_count+1}/{max_retries}")
                time.sleep(1)
                retry_count += 1
                
            if not self.trader.is_connected():
                raise TradingError("交易连接建立超时")
            
            # 订阅交易推送
            if not self.trader.subscribe(self.account):
                raise TradingError(f"订阅账户 {self.account.account_id} 失败")
            
            self.connected = True
            logger.info(f"交易接口初始化成功 - 账户: {self.account.account_id}")
            
        except Exception as e:
            self.connected = False
            self.stats['connection_errors'] += 1
            logger.error(f"交易接口初始化失败: {str(e)}")
            raise TradingError(f"交易接口初始化失败: {str(e)}")
    
    def run(self, strategy: BaseStrategy) -> None:
        """运行交易引擎

        Args:
            strategy: 策略实例
        """
        try:
            logger.info(f"启动交易引擎 - 策略: {strategy.name}")
            
            # 检查交易连接状态
            if not self._check_connection():
                logger.warning("交易连接已断开，尝试重新连接")
                self._reconnect()
                
            # 更新账户信息
            self._update_account_info()
            
            # 运行策略
            while True:
                # 检查是否为交易时段
                if not strategy.data_fetcher.is_trading_time():
                    continue
                
                # 获取市场数据
                start_time = time.time()
                data = self._get_market_data(strategy)
                if not data:
                    continue
                data_time = time.time() - start_time
                
                # 运行策略
                start_time = time.time()
                strategy.on_bar(data)
                strategy_time = time.time() - start_time
                
                # 记录性能统计
                logger.debug(f"性能统计 - 数据获取: {data_time:.3f}秒, 策略执行: {strategy_time:.3f}秒")
                
                # 更新交易状态
                self._update_trading_status()
                
                # 保存交易状态
                self._save_trading_state()
                
        except TradingError as e:
            logger.error(f"交易引擎运行错误: {str(e)}")
            # 尝试恢复交易状态
            self._load_trading_state()
            raise
        except Exception as e:
            logger.error(f"交易引擎运行未知错误: {str(e)}")
            # 尝试恢复交易状态
            self._load_trading_state()
            raise
        finally:
            self.trader.stop()
            
    def _check_connection(self) -> bool:
        """检查交易连接状态
        
        Returns:
            bool: 连接是否正常
        """
        try:
            if not self.trader.is_connected():
                self.connected = False
                return False
                
            # 检查最后更新时间，如果超过5分钟未更新，认为连接异常
            if self.last_update_time and \
               (datetime.now() - self.last_update_time).total_seconds() > 300:
                logger.warning("交易状态长时间未更新，可能连接异常")
                self.connected = False
                return False
                
            return True
        except Exception as e:
            logger.error(f"检查交易连接状态失败: {str(e)}")
            self.connected = False
            return False
            
    @retry_on_error(max_attempts=3, delay=5.0)
    def _reconnect(self) -> bool:
        """重新连接交易接口
        
        Returns:
            bool: 重连是否成功
        """
        try:
            # 先停止现有连接
            self.trader.stop()
            time.sleep(2)
            
            # 重新初始化
            self._init_trader()
            
            # 更新统计信息
            self.stats['reconnect_count'] += 1
            
            return self.connected
        except Exception as e:
            logger.error(f"重新连接交易接口失败: {str(e)}")
            return False
            
    def _save_trading_state(self) -> None:
        """保存交易状态到缓存"""
        try:
            state = {
                'orders': self.orders,
                'positions': self.positions,
                'assets': self.assets,
                'timestamp': datetime.now(),
                'stats': self.stats
            }
            
            cache_path = os.path.join(self.cache_dir, 'trading_state.pkl')
            with open(cache_path, 'wb') as f:
                pickle.dump(state, f)
                
            logger.debug("交易状态已保存到缓存")
        except Exception as e:
            logger.error(f"保存交易状态失败: {str(e)}")
            
    def _load_trading_state(self) -> bool:
        """从缓存加载交易状态
        
        Returns:
            bool: 是否成功加载
        """
        try:
            cache_path = os.path.join(self.cache_dir, 'trading_state.pkl')
            if not os.path.exists(cache_path):
                logger.warning("交易状态缓存不存在，无法恢复")
                return False
                
            with open(cache_path, 'rb') as f:
                state = pickle.load(f)
                
            # 检查缓存是否过期（超过1小时）
            if (datetime.now() - state['timestamp']).total_seconds() > 3600:
                logger.warning("交易状态缓存已过期，无法恢复")
                return False
                
            self.orders = state['orders']
            self.positions = state['positions']
            self.assets = state['assets']
            self.stats = state['stats']
            
            logger.info("已从缓存恢复交易状态")
            return True
        except Exception as e:
            logger.error(f"加载交易状态失败: {str(e)}")
            return False
    
    @retry_on_error(max_attempts=3, delay=1.0)
    def _get_market_data(self, strategy: BaseStrategy) -> Dict[str, Any]:
        """获取市场数据

        Args:
            strategy: 策略实例

        Returns:
            Dict[str, Any]: 市场数据字典
        """
        try:
            # 获取当前时间
            now = datetime.now()
            
            # 尝试从缓存加载数据
            cache_key = f"{strategy.name}_{now.strftime('%Y%m%d_%H%M')}"
            cached_data = self._get_cached_data(cache_key)
            if cached_data:
                logger.debug(f"从缓存加载市场数据: {cache_key}")
                return cached_data
            
            # 获取实时数据
            data = {}
            data_errors = 0
            for code in strategy.universe:
                try:
                    market_data = strategy.data_fetcher.get_realtime_data(code)
                    if market_data:
                        data[code] = market_data
                    else:
                        logger.warning(f"获取实时数据失败: {code}")
                        data_errors += 1
                except Exception as e:
                    logger.error(f"获取实时数据异常: {code}, {str(e)}")
                    data_errors += 1
            
            # 如果大部分数据获取失败，可能是连接问题
            if data_errors > len(strategy.universe) * 0.5:
                logger.error(f"大部分数据获取失败 ({data_errors}/{len(strategy.universe)}), 可能是连接问题")
                self.connected = False
                raise TradingError("数据获取失败率过高")
            
            # 缓存市场数据
            self._cache_market_data(cache_key, data)
            
            return data
            
        except TradingError as e:
            logger.error(f"获取市场数据失败: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"获取市场数据未知错误: {str(e)}")
            return {}
            
    def _get_cached_data(self, cache_key: str) -> Dict[str, Any]:
        """从缓存获取市场数据
        
        Args:
            cache_key: 缓存键
            
        Returns:
            Dict[str, Any]: 缓存的市场数据，如果不存在则返回None
        """
        try:
            cache_path = os.path.join(self.cache_dir, f"market_{cache_key}.pkl")
            if not os.path.exists(cache_path):
                return None
                
            # 检查缓存是否过期（超过5分钟）
            if time.time() - os.path.getmtime(cache_path) > 300:
                logger.debug(f"缓存已过期: {cache_key}")
                return None
                
            with open(cache_path, 'rb') as f:
                data = pickle.load(f)
                return data
        except Exception as e:
            logger.error(f"读取缓存数据失败: {str(e)}")
            return None
            
    def _cache_market_data(self, cache_key: str, data: Dict[str, Any]) -> None:
        """缓存市场数据
        
        Args:
            cache_key: 缓存键
            data: 市场数据
        """
        try:
            cache_path = os.path.join(self.cache_dir, f"market_{cache_key}.pkl")
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
                
            logger.debug(f"市场数据已缓存: {cache_key}")
        except Exception as e:
            logger.error(f"缓存市场数据失败: {str(e)}")
    
    @retry_on_error(max_attempts=3, delay=1.0)
    def _update_account_info(self) -> bool:
        """更新账户信息
        
        Returns:
            bool: 更新是否成功
        """
        try:
            # 查询资金信息
            assets = self.trader.query_stock_assets(self.account)
            if not assets:
                logger.error("获取资产信息失败")
                return False
                
            self.assets = assets
            self.last_update_time = datetime.now()
                
            trade_log(f"账户资金 - 总资产: {assets.total_asset:.2f}, "
                     f"可用资金: {assets.cash:.2f}")
            
            # 查询持仓信息
            positions = self.trader.query_stock_positions(self.account)
            if not positions and self.positions:
                logger.warning("获取持仓信息为空，但当前有记录的持仓，可能是接口问题")
                # 不更新持仓信息，保留之前的记录
            elif positions:
                old_positions = self.positions.copy()
                self.positions = {}
                for pos in positions:
                    self.positions[pos.stock_code] = pos.volume
                    trade_log(f"账户持仓 - 代码: {pos.stock_code}, "
                             f"数量: {pos.volume}, 可用: {pos.can_use_volume}")
                    
                # 检查持仓变化
                for code, volume in self.positions.items():
                    if code in old_positions:
                        if volume != old_positions[code]:
                            logger.info(f"持仓变化 - {code}: {old_positions[code]} -> {volume}")
                    else:
                        logger.info(f"新增持仓 - {code}: {volume}")
                        
                for code, volume in old_positions.items():
                    if code not in self.positions:
                        logger.info(f"清空持仓 - {code}")
            
            return True
            
        except Exception as e:
            logger.error(f"更新账户信息失败: {str(e)}")
            return False
    
    @retry_on_error(max_attempts=3, delay=1.0)
    def _update_trading_status(self) -> bool:
        """更新交易状态
        
        Returns:
            bool: 更新是否成功
        """
        try:
            # 查询未完成订单
            orders = self.trader.query_stock_orders(self.account, False)
            if orders is None:
                logger.error("获取委托信息失败")
                return False
                
            self.last_update_time = datetime.now()
            
            # 更新委托状态
            old_orders = self.orders.copy() if self.orders else {}
            self.orders = {}
            for order in orders:
                if order.order_status not in ['已成交', '已撤单', '已拒绝']:
                    self.orders[order.order_id] = order
                    # 检查订单超时
                    order_time = datetime.strptime(order.order_time, '%H:%M:%S')
                    if (datetime.now() - order_time).seconds > self.config['trading']['order_timeout']:
                        # 撤销超时订单
                        self.trader.cancel_order_stock(self.account, order.order_id)
                        trade_log(f"撤销超时订单 - 委托号: {order.order_id}")
            
            # 检查委托变化
            for order_id, order in self.orders.items():
                if order_id in old_orders:
                    old_status = old_orders[order_id].order_status
                    if order.order_status != old_status:
                        logger.info(f"委托状态变化 - ID: {order_id}, {old_status} -> {order.order_status}")
                else:
                    logger.info(f"新增委托 - ID: {order_id}, 状态: {order.order_status}")
            
            if self.orders:
                logger.info(f"当前活跃委托数量: {len(self.orders)}")
                logger.debug(f"活跃委托详情: {[f'{o.stock_code}:{o.order_status}' for o in self.orders.values()]}")
            
            return True
            
        except Exception as e:
            logger.error(f"更新交易状态失败: {str(e)}")
            return False
    
    @retry_on_error(max_attempts=2, delay=0.5)
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
            # 检查交易连接状态
            if not self._check_connection():
                logger.error("交易连接已断开，无法下单")
                return False
                
            # 检查是否可交易
            if not self._check_tradable(code, direction, volume):
                return False
            
            # 更新统计信息
            self.stats['order_count'] += 1
            start_time = time.time()
            
            # 执行下单
            if direction == 'buy':
                order_id = self.trader.order_stock(self.account, code, price, volume, 'buy')
            else:
                order_id = self.trader.order_stock(self.account, code, price, volume, 'sell')
            
            # 记录下单耗时
            order_time = time.time() - start_time
            logger.debug(f"下单耗时: {order_time:.3f}秒")
            
            if order_id:
                trade_log(f"下单成功 - 代码: {code}, 方向: {direction}, "
                         f"数量: {volume}, 价格: {price:.3f}, 委托号: {order_id}")
                self.stats['success_count'] += 1
                
                # 立即更新交易状态
                self._update_trading_status()
                return True
            else:
                logger.error(f"下单失败 - 代码: {code}, 方向: {direction}")
                self.stats['fail_count'] += 1
                return False
            
        except TradingError as e:
            logger.error(f"下单执行错误: {str(e)}")
            self.stats['fail_count'] += 1
            return False
        except Exception as e:
            logger.error(f"下单执行未知错误: {str(e)}")
            self.stats['fail_count'] += 1
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
            # 检查交易连接状态
            if not self.connected:
                logger.warning("交易连接未建立或已断开")
                return False
                
            # 检查代码格式
            if not code or len(code) < 6:
                logger.warning(f"无效的股票代码: {code}")
                return False
                
            # 检查交易方向
            if direction not in ['buy', 'sell']:
                logger.warning(f"无效的交易方向: {direction}")
                return False
                
            # 检查交易数量
            if volume <= 0 or volume % 100 != 0:
                logger.warning(f"无效的交易数量: {volume}，必须为100的整数倍")
                return False
            
            # 检查账户资产
            if not self.assets:
                logger.warning("账户资产信息不可用")
                return False
                
            # 检查持仓限制
            if direction == 'buy':
                # 检查资金是否充足（预估）
                if self.assets.cash < volume * price * 1.01:  # 考虑手续费
                    logger.warning(f"资金不足 - 所需: {volume * price * 1.01:.2f}, 可用: {self.assets.cash:.2f}")
                    return False
                    
                # 检查持仓数量限制
                if len(self.positions) >= self.trading_config['max_positions'] \
                        and code not in self.positions:
                    logger.warning(f"超过最大持仓限制: {self.trading_config['max_positions']}")
                    return False
                    
                # 检查单只股票资金比例限制
                position_limit = self.trading_config.get('single_position_limit', 0.2)
                if volume * price > self.assets.total_asset * position_limit:
                    logger.warning(f"超过单只股票资金比例限制: {position_limit * 100}%")
                    return False
            else:  # 卖出
                # 检查持仓是否存在
                if code not in self.positions:
                    logger.warning(f"持仓不存在 - 代码: {code}")
                    return False
                    
                # 检查持仓是否足够
                if self.positions[code] < volume:
                    logger.warning(f"持仓不足 - 代码: {code}, 所需: {volume}, "
                                 f"现有: {self.positions.get(code, 0)}")
                    return False
            
            # 检查是否有重复委托
            for order_id, order in self.orders.items():
                if order.stock_code == code and order.order_direction == direction:
                    logger.warning(f"存在未完成的同向委托 - 代码: {code}, 方向: {direction}")
                    # 不阻止交易，只是警告
            
            return True
            
        except Exception as e:
            logger.error(f"交易检查失败: {str(e)}")
            return False