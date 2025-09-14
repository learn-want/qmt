import datetime
import numpy as np
from xtquant import xtdata
from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from xtquant.xttype import StockAccount
from xtquant import xtconstant
import time
import pandas as pd

accID = '40126980'   # 填写你的资金账号

class MyContext:
    def __init__(self):
        self.today_stock_list = []

class MyStrategy(XtQuantTraderCallback):
    def __init__(self):
        self.ctx = MyContext()
        self.trader = XtQuantTrader(r'C:\国金证券QMT交易端\userdata_mini', 123456)
        self.trader.register_callback(self)
        self.trader.start()
        self.trader.connect()
        self.acc = StockAccount(accID, 'STOCK')

        account_res = self.trader.query_stock_asset(self.acc)
        print('account_res', account_res)

        if account_res is None:
            print('account_res 为空了')
        else:
            print('连接成功')

        available_funds = account_res.cash
        print('可用资金为：', available_funds)
    
    def run(self):
        today_stock_list = ['000001.SZ', '000002.SZ']
        stock_info = xtdata.get_full_tick(today_stock_list)
        # print(stock_info)

        for i in range(0, len(today_stock_list)):
            stock = today_stock_list[i]
            if stock not in stock_info:
                continue

            tick = stock_info[stock]
            lastPrice = tick.get('lastPrice')
            bidPrice = tick.get('bidPrice', [0])[0]
            bidVol = tick.get('bidVol', [0])[0]

            detail = xtdata.get_instrument_detail(stock)
            # print('detail', detail)
            UpStopPrice = detail.get('UpStopPrice', 0)
            DownStopPrice = detail.get('DownStopPrice', 0)

            print('stock:', stock,
                'lastPrice:', lastPrice,
                'bidPrice:', bidPrice,
                'bidVol:', bidVol,
                'UpStopPrice:', UpStopPrice,
                'DownStopPrice:', DownStopPrice)


if __name__ == '__main__':
    strategy = MyStrategy()
    strategy.run()