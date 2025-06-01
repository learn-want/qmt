#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
A股市场主板首板打板策略

此策略基于A股市场主板的首板特性，通过识别涨停板和相关技术指标来进行交易决策：
1. 识别当日涨停的个股，判断是否为首板
2. 分析涨停板的强度、成交量、换手率等特征
3. 根据市场环境和个股特征决定是否参与打板
4. 设置严格的止盈止损策略控制风险
"""

from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger

from strategies.base_strategy import BaseStrategy
from utils.logger import strategy_log

class FirstBoardStrategy(BaseStrategy):
    """A股市场主板首板打板策略"""

    def initialize(self) -> None:
        """策略初始化"""
        # 获取策略参数
        self.limit_up_pct = self.params.get('limit_up_pct', 0.097)  # 涨停判断阈值，略小于10%以避免误差
        self.volume_ratio = self.params.get('volume_ratio', 2.0)    # 成交量放大倍数要求
        self.turnover_rate = self.params.get('turnover_rate', 5.0)  # 换手率最小要求
        self.max_boards = self.params.get('max_boards', 1)          # 最大连板数，首板为1
        self.stop_loss_pct = self.params.get('stop_loss_pct', 0.03)  # 止损比例
        self.stop_profit_pct = self.params.get('stop_profit_pct', 0.05)  # 止盈比例
        self.max_position_pct = self.params.get('max_position_pct', 0.2)  # 单只股票最大仓位
        
        # 记录已识别的涨停板股票
        self.limit_up_stocks = {}
        
        strategy_log(self.name, f"策略初始化 - 参数: 涨停阈值={self.limit_up_pct}, "
                             f"成交量比={self.volume_ratio}, 换手率={self.turnover_rate}, "
                             f"最大连板数={self.max_boards}, 止损比例={self.stop_loss_pct}, "
                             f"止盈比例={self.stop_profit_pct}, 最大仓位={self.max_position_pct}")

    def generate_signals(self, data: pd.DataFrame) -> Dict[str, float]:
        """生成交易信号

        Args:
            data: 市场数据

        Returns:
            Dict[str, float]: 交易信号字典，键为股票代码，值为仓位比例（-1到1）
        """
        try:
            signals = {}
            
            # 获取最新交易日数据
            latest_date = data.index[-1].strftime('%Y%m%d')
            
            # 遍历股票池
            for code in self.universe:
                # 获取个股数据
                stock_data = self._get_stock_data(code, latest_date)
                if stock_data.empty:
                    continue
                
                # 判断是否为首板
                is_first_board, board_strength = self._check_first_board(stock_data)
                
                # 生成交易信号
                signal = 0.0
                
                # 买入条件：确认为首板且强度足够
                if is_first_board and board_strength > 0.7:
                    # 检查市场环境
                    if self._check_market_condition():
                        signal = self.max_position_pct
                        strategy_log(self.name, f"买入信号 - {code}: 首板打板, 强度={board_strength:.2f}")
                        # 记录涨停板信息
                        self.limit_up_stocks[code] = {
                            'date': latest_date,
                            'price': stock_data['close'].iloc[-1],
                            'strength': board_strength
                        }
                
                # 卖出条件：止盈或止损
                elif code in self.positions:
                    # 获取持仓信息
                    position = self.positions[code]
                    entry_price = position['price']
                    current_price = stock_data['close'].iloc[-1]
                    price_change = (current_price - entry_price) / entry_price
                    
                    # 止盈条件
                    if price_change >= self.stop_profit_pct:
                        signal = -1.0
                        strategy_log(self.name, f"卖出信号 - {code}: 止盈, 收益率={price_change:.2%}")
                    
                    # 止损条件
                    elif price_change <= -self.stop_loss_pct:
                        signal = -1.0
                        strategy_log(self.name, f"卖出信号 - {code}: 止损, 收益率={price_change:.2%}")
                    
                    # 次日高开未能继续涨停，及时卖出
                    elif code in self.limit_up_stocks and latest_date > self.limit_up_stocks[code]['date']:
                        if not self._check_continue_limit_up(stock_data):
                            signal = -1.0
                            strategy_log(self.name, f"卖出信号 - {code}: 次日未能继续涨停")
                
                signals[code] = signal
            
            return signals
            
        except Exception as e:
            logger.error(f"信号生成错误 - {self.name}: {str(e)}")
            return {}

    def _get_stock_data(self, code: str, date: str) -> pd.DataFrame:
        """获取个股历史数据

        Args:
            code: 股票代码
            date: 当前日期

        Returns:
            pd.DataFrame: 个股历史数据
        """
        try:
            # 获取历史数据，增加获取的天数以确保有足够的历史数据进行分析
            history_data = self.data_fetcher.get_history_data(
                code, 
                period='1d', 
                count=30,  # 增加获取的历史数据天数
                fields=['open', 'high', 'low', 'close', 'volume', 'amount', 'turnover_rate', 'total_shares', 'float_shares']
            )
            
            if not history_data or code not in history_data:
                strategy_log(self.name, f"无法获取{code}的历史数据")
                return pd.DataFrame()
            
            # 转换为DataFrame
            stock_data = pd.DataFrame({
                'open': history_data[code]['open'],
                'high': history_data[code]['high'],
                'low': history_data[code]['low'],
                'close': history_data[code]['close'],
                'volume': history_data[code]['volume'],
                'amount': history_data[code]['amount'],
                'time': history_data[code]['time']
            })
            
            # 设置日期索引
            stock_data['date'] = pd.to_datetime(stock_data['time'], format='%Y%m%d')
            stock_data.set_index('date', inplace=True)
            
            # 计算前收盘价
            stock_data['pre_close'] = stock_data['close'].shift(1)
            
            # 计算涨跌幅
            stock_data['pct_change'] = (stock_data['close'] - stock_data['pre_close']) / stock_data['pre_close'] * 100
            
            # 计算涨停价和跌停价（主板股票涨跌幅限制为10%，ST股票为5%）
            # 这里简化处理，假设所有股票都是主板非ST股票
            stock_data['limit_up_price'] = np.round(stock_data['pre_close'] * 1.1, 2)  # 涨停价四舍五入到分
            stock_data['limit_down_price'] = np.round(stock_data['pre_close'] * 0.9, 2)  # 跌停价四舍五入到分
            
            # 计算成交量变化
            stock_data['volume_ratio'] = stock_data['volume'] / stock_data['volume'].shift(1)
            
            # 计算换手率
            # 尝试从history_data中获取换手率数据
            if 'turnover_rate' in history_data[code]:
                stock_data['turnover_rate'] = history_data[code]['turnover_rate']
            else:
                # 尝试获取流通股本数据
                try:
                    # 获取股票基本信息
                    stock_info = self.data_fetcher.get_instrument_detail(code)
                    if stock_info and 'float_shares' in stock_info:
                        float_shares = stock_info['float_shares']
                        # 计算换手率 = 成交量 / 流通股本 * 100%
                        stock_data['turnover_rate'] = stock_data['volume'] / float_shares * 100
                    else:
                        # 简化处理，使用成交量的相对大小估算换手率
                        stock_data['turnover_rate'] = stock_data['volume'] / stock_data['volume'].rolling(20).mean() * 5
                except Exception as e:
                    logger.warning(f"获取{code}流通股本失败，使用简化方法计算换手率: {str(e)}")
                    stock_data['turnover_rate'] = stock_data['volume'] / stock_data['volume'].rolling(20).mean() * 5
            
            # 计算技术指标
            # 移动平均线
            stock_data['ma5'] = stock_data['close'].rolling(5).mean()
            stock_data['ma10'] = stock_data['close'].rolling(10).mean()
            stock_data['ma20'] = stock_data['close'].rolling(20).mean()
            
            # 计算量比（当日成交量/过去5日平均成交量）
            stock_data['volume_ma5'] = stock_data['volume'].rolling(5).mean()
            stock_data['volume_ratio_5'] = stock_data['volume'] / stock_data['volume_ma5']
            
            # 标记是否涨停
            stock_data['is_limit_up'] = (stock_data['close'] >= stock_data['limit_up_price'] * 0.997) | \
                                       (stock_data['pct_change'] >= self.limit_up_pct * 100)
            
            strategy_log(self.name, f"获取{code}历史数据成功，数据长度={len(stock_data)}")
            return stock_data
            
        except Exception as e:
            logger.error(f"获取股票数据失败 - {code}: {str(e)}")
            return pd.DataFrame()

    def _check_first_board(self, data: pd.DataFrame) -> Tuple[bool, float]:
        """判断是否为首板

        Args:
            data: 个股历史数据

        Returns:
            Tuple[bool, float]: (是否为首板, 涨停强度)
        """
        try:
            # 确保有足够的历史数据
            if len(data) < 20:
                return False, 0.0
            
            latest_data = data.iloc[-1]
            prev_data = data.iloc[-2]
            history_data = data.iloc[:-1]  # 不包括最新交易日的历史数据
            
            # 判断当日是否涨停
            is_limit_up = latest_data['pct_change'] >= self.limit_up_pct * 100
            
            if not is_limit_up:
                return False, 0.0
            
            # 判断历史上是否有涨停（过去20个交易日内）
            limit_up_days = history_data[history_data['pct_change'] >= self.limit_up_pct * 100].index.tolist()
            
            # 计算涨停强度指标
            # 1. 成交量放大倍数
            volume_ratio = latest_data['volume'] / prev_data['volume'] if prev_data['volume'] > 0 else 0
            volume_strength = min(volume_ratio / self.volume_ratio, 1.5) / 1.5
            
            # 2. 换手率
            turnover_rate = latest_data['turnover_rate']
            turnover_strength = min(turnover_rate / self.turnover_rate, 2.0) / 2.0
            
            # 3. 涨停时间特征（这里简化处理，实际应使用分时数据）
            # 假设收盘价接近最高价表示涨停封板时间较长
            price_strength = (latest_data['close'] - latest_data['open']) / (latest_data['high'] - latest_data['open']) if (latest_data['high'] - latest_data['open']) > 0 else 0
            
            # 4. 涨停前的走势（低吸还是冲高）
            # 计算5日均线
            data['ma5'] = data['close'].rolling(5).mean()
            ma5_position = latest_data['close'] / latest_data['ma5'] if not pd.isna(latest_data['ma5']) and latest_data['ma5'] > 0 else 1
            trend_strength = min(ma5_position / 1.05, 1.2) / 1.2
            
            # 综合强度评分 (0-1)
            board_strength = (
                volume_strength * 0.4 +   # 成交量权重40%
                turnover_strength * 0.3 + # 换手率权重30%
                price_strength * 0.2 +    # 涨停时间特征权重20%
                trend_strength * 0.1      # 走势特征权重10%
            )
            
            # 判断是否为首板（20个交易日内无涨停记录）
            is_first_board = is_limit_up and len(limit_up_days) == 0
            
            # 记录详细日志
            strategy_log(self.name, f"首板检查: 股票涨停={is_limit_up}, 历史涨停次数={len(limit_up_days)}, "
                                 f"成交量强度={volume_strength:.2f}, 换手率强度={turnover_strength:.2f}, "
                                 f"综合强度={board_strength:.2f}, 是否首板={is_first_board}")
            
            return is_first_board, board_strength
            
        except Exception as e:
            logger.error(f"首板判断失败: {str(e)}")
            return False, 0.0

    def _check_market_condition(self) -> bool:
        """检查市场环境是否适合打板

        Returns:
            bool: 市场环境是否良好
        """
        try:
            # 获取大盘指数数据（以上证指数为例）
            index_code = '000001.SH'
            index_data = self.data_fetcher.get_history_data(index_code, period='1d', count=10)
            if not index_data or index_code not in index_data:
                return False
            
            # 转换为DataFrame
            df = pd.DataFrame({
                'open': index_data[index_code]['open'],
                'high': index_data[index_code]['high'],
                'low': index_data[index_code]['low'],
                'close': index_data[index_code]['close'],
                'volume': index_data[index_code]['volume'],
                'time': index_data[index_code]['time']
            })
            
            # 计算大盘涨跌幅
            df['pct_change'] = df['close'].pct_change() * 100
            
            # 计算5日均线
            df['ma5'] = df['close'].rolling(5).mean()
            
            # 判断大盘环境
            latest_data = df.iloc[-1]
            
            # 1. 大盘当日涨跌幅>-1%
            condition1 = latest_data['pct_change'] > -1.0
            
            # 2. 大盘收盘价在5日均线之上
            condition2 = latest_data['close'] > latest_data['ma5'] if not pd.isna(latest_data['ma5']) else True
            
            # 3. 大盘成交量较前一日放大
            condition3 = latest_data['volume'] > df.iloc[-2]['volume'] if len(df) > 1 else True
            
            # 综合判断市场环境
            is_market_good = condition1 and condition2
            
            strategy_log(self.name, f"市场环境检查: 涨跌幅={latest_data['pct_change']:.2f}%, "
                                 f"MA5={condition2}, 成交量={condition3}, 结果={is_market_good}")
            
            return is_market_good
            
        except Exception as e:
            logger.error(f"市场环境检查失败: {str(e)}")
            return False

    def _check_continue_limit_up(self, data: pd.DataFrame) -> bool:
        """检查是否有继续涨停的趋势

        Args:
            data: 个股历史数据

        Returns:
            bool: 是否有继续涨停的趋势
        """
        try:
            # 确保有足够的历史数据
            if len(data) < 20:
                return False
                
            # 获取最新交易日数据
            latest_data = data.iloc[-1]
            
            # 1. 判断当前是否已经涨停
            is_limit_up = latest_data['pct_change'] >= self.limit_up_pct * 100
            if is_limit_up:
                return True  # 已经涨停，直接返回True
            
            # 2. 计算MACD指标
            if 'MACD' not in data.columns or 'MACD_signal' not in data.columns:
                # 计算MACD
                ema12 = data['close'].ewm(span=12, adjust=False).mean()
                ema26 = data['close'].ewm(span=26, adjust=False).mean()
                data['MACD'] = ema12 - ema26
                data['MACD_signal'] = data['MACD'].ewm(span=9, adjust=False).mean()
                data['MACD_hist'] = data['MACD'] - data['MACD_signal']
            
            # 3. 计算RSI指标
            if 'RSI' not in data.columns:
                # 计算RSI
                delta = data['close'].diff()
                gain = delta.where(delta > 0, 0)
                loss = -delta.where(delta < 0, 0)
                avg_gain = gain.rolling(window=14).mean()
                avg_loss = loss.rolling(window=14).mean()
                rs = avg_gain / avg_loss
                data['RSI'] = 100 - (100 / (1 + rs))
            
            # 4. 分析技术指标
            # MACD金叉或柱状图由负转正
            macd_golden_cross = False
            if len(data) >= 3:
                macd_golden_cross = (data['MACD'].iloc[-1] > data['MACD_signal'].iloc[-1]) and \
                                   (data['MACD'].iloc[-2] <= data['MACD_signal'].iloc[-2])
            
            macd_hist_positive = data['MACD_hist'].iloc[-1] > 0 if 'MACD_hist' in data.columns else False
            
            # RSI上升且大于50
            rsi_bullish = False
            if 'RSI' in data.columns and len(data) >= 2:
                rsi_bullish = (data['RSI'].iloc[-1] > data['RSI'].iloc[-2]) and (data['RSI'].iloc[-1] > 50)
            
            # 5. 分析K线形态
            # 收盘价高于开盘价（阳线）
            bullish_candle = latest_data['close'] > latest_data['open']
            
            # 收盘价创近期新高
            price_new_high = latest_data['close'] >= data['close'][-5:].max()
            
            # 6. 综合判断
            # 至少满足3个条件
            conditions_met = sum([macd_golden_cross, macd_hist_positive, rsi_bullish, bullish_candle, price_new_high])
            has_uptrend = conditions_met >= 3
            
            strategy_log(self.name, f"涨停趋势检查: MACD金叉={macd_golden_cross}, MACD柱状图正={macd_hist_positive}, "
                                 f"RSI看涨={rsi_bullish}, 阳线={bullish_candle}, 价格新高={price_new_high}, "
                                 f"结果={has_uptrend}")
            
            return has_uptrend
            
        except Exception as e:
            logger.error(f"涨停延续检查失败: {str(e)}")
            return False

    def _calculate_position(self, code: str, signal: float) -> float:
        """计算目标仓位，重写父类方法

        Args:
            code: 股票代码
            signal: 交易信号

        Returns:
            float: 目标仓位
        """
        # 继承父类的仓位控制逻辑
        target_pos = super()._calculate_position(code, signal)
        
        # 限制单只股票的最大仓位
        if target_pos > 0:
            target_pos = min(target_pos, self.max_position_pct)
        
        return target_pos