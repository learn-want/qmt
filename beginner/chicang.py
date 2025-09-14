import datetime
import numpy as np
from xtquant import xtdata
from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from xtquant.xttype import StockAccount
from xtquant import xtconstant
import time
import pandas as pd
aCCID = '40126980'
#填写你的资金账号
class MyContext:
    def __init__(self):
        pass
class MyStrategy(XtQuantTraderCallback):
    def __init__(self):
        self.ctx = MyContext()
        self.trader = XtQuantTrader(r'C:\国金证券QMT交易端\userdata_mini', 123456)
        self.trader.register_callback(self)
        self.trader.start()
        self.trader.connect()
        self.acc = StockAccount(aCCID, 'STOCK')
        account_res = self.trader.query_stock_asset(self.acc)
        print('account_res', account_res)
        if account_res is None:
            print('account_res空了')
        else:
            print('连接正常')
        # available_funds = account_res.cash
        # print('可用余额：', available_funds)
        # positions = self.get_position()
        # print('positions', positions)
        # for index, row in positions.iterrows():  # 通历 DataFrame 的行 （Series）
        #     print(row)
        positions = self.get_position('888880.SH')
        print('positions', positions)
    def get_position(self, stock_code=None):
        """
        查询持仓信息
        :param stock_code: 股票代码，None 表示查询所有持仓
        :return: 单个持仓的字典或所有持仓的 DataFrame
        """
        if stock_code:
            # 查询指定股票持仓
            position = self.trader.query_stock_position(self.acc, stock_code)
            if position:
                return {
                    '证券代码': position.stock_code,     # 股票代码
                    '成本价': position.open_price,       # 持仓成本价
                    '持仓数量': position.volume,         # 当前持仓数量
                    '可用数量': position.can_use_volume, # 可用的数量
                    '冻结数量': position.frozen_volume,  # 冻结的数量
                    '市值': position.market_value        # 持仓市值
                }
            return None
        else:
            # 查询所有持仓
            positions = self.trader.query_stock_positions(self.acc)
            if positions:
                pos_list = []
                for pos in positions:
                    pos_list.append({
                        '证券代码': pos.stock_code,
                        '成本价': pos.open_price,
                        '持仓数量': pos.volume,
                        '可用数量': pos.can_use_volume,
                        '冻结数量': pos.frozen_volume,
                        '市值': pos.market_value
                    })
                return pd.DataFrame(pos_list)
            return pd.DataFrame()  # 空仓时返回空 DataFrame

if __name__ == '__main__':
    strategy = MyStrategy()
    # strategy.run()  # 运行策略