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
        print('account_res:', account_res)

        if account_res is None:
            print('account_res 为空了')
        else:
            print('连接正常')

        available_funds = account_res.cash
        print('可用余额：', available_funds)

    def run(self):
        today_stock_list = ['000001.SZ']
        stock_info = xtdata.get_full_tick(today_stock_list)
        print(stock_info)

        for i in range(0, len(today_stock_list)):
            stock = today_stock_list[i]
            if stock not in stock_info:
                continue

            tick = stock_info[stock]
            lastPrice = tick.get('lastPrice')
            askPrice = tick.get('askPrice', [0])[0]
            askVol = tick.get('askVol', [0])[0]

            detail = xtdata.get_instrument_detail(stock)
            print('detail', detail)
            UpStopPrice = detail.get('UpStopPrice', 0)
            DownStopPrice = detail.get('DownStopPrice', 0)

            print('stock', stock,
                'lastPrice:', lastPrice,
                'askPrice:', askPrice,
                'askVol:', askVol,
                'UpStopPrice:', UpStopPrice,
                'DownStopPrice:', DownStopPrice)

            sell_num = 100 #100股
            sell_price = tick.get('askPrice', [0])[4] #卖五价
            #要成较快，使用买一价
            # sell_price = tick.get('bidPrice', [0])[0] # 卖一价

            order_id = self.trader.order_stock(
                self.acc,
                stock,
                xtconstant.STOCK_SELL,     # 买入
                sell_num,                  # 买入数量
                xtconstant.FIX_PRICE,     # 限价单
                sell_price,                # 价格
                # strategy_name='测试策略',
                # remark='测试限价单'
            )

            print("下单成功", 'order_id', order_id,
                'stock', stock,
                'buy_num', sell_num,
                'buy_price', sell_price)


if __name__ == '__main__':
    strategy = MyStrategy()
    strategy.run()