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
    
    def handle_cancel_orders(self):
        # 获取委托单
        orders = self.query_orders()   # 返回 DataFrame
        # print('orders:', orders)
        if orders is None or orders.empty:
            print('当前没有未成交订单')
            return 
        for _, order in orders.iterrows():   # 遍历 DataFrame 的行 (Series)
            print('order:', order)
            ordercode = order.委托编号      # 正确写法
            print('ordercode:', ordercode)

            if order.状态 == 50 or order.状态 == 55:
                print('order.时间', order.时间)
                order_time = datetime.datetime.fromtimestamp(order.时间)
                now = datetime.datetime.now()
                if (now - order_time).seconds > 10 and order.委托编号:
                    self.trader.cancel_order_stock(self.acc, order.委托编号)
                    print('撤单合约编号', order.委托编号, '股票代码', order.证券代码)
    
    def query_orders(self, order_id=None):
        """
        查询订单状态
        :param order_id: 指定订单号查询，None 表示查询所有订单
        :return: 单个订单字典或所有订单 DataFrame
        """
        if order_id:
            # 查询指定订单
            order = self.trader.query_stock_order(self.trader, order_id)
            if order:
                return {
                    '委托编号': order.order_id,       # 订单ID
                    '证券代码': order.stock_code,    # 股票代码
                    '委托价格': order.price,         # 委托价格
                    '委托数量': order.order_volume,  # 委托数量
                    '成交数量': order.traded_volume, # 已成交量
                    '状态': order.order_status,      # 委托状态
                    '时间': order.order_time         # 委托时间
                }
            return None
        else:
            # 查询所有订单
            orders = self.trader.query_stock_orders(self.acc)
            if orders:
                order_list = []
                for order in orders:
                    order_list.append({
                        '委托编号': order.order_id,
                        '证券代码': order.stock_code,
                        '委托价格': order.price,
                        '委托数量': order.order_volume,
                        '成交数量': order.traded_volume,
                        '状态': order.order_status,
                        '时间': order.order_time
                    })
                return pd.DataFrame(order_list)
            

if __name__ == '__main__':
    strategy = MyStrategy()
    while True:
        strategy.handle_cancel_orders()
        time.sleep(5)