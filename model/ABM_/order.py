import time

class Order:

    def __init__(self, trader_id, order_type, stock_symbol, price, quantity, is_buy, timestamp=None, order_id=None):
        self.order_id = order_id
        self.trader_id = trader_id
        self.order_type = order_type    # 0为限价单，1为市价单
        self.stock_symbol = stock_symbol
        self.price = price
        self.quantity = quantity
        self.is_buy = is_buy  # True for buy, False for sell
        self.timestamp = timestamp if timestamp else time.time()  # 默认使用创建订单的时间

    def __repr__(self):
        # return f"Order({self.trader_id}, {'Limit' if self.order_type == 0 else 'Market'}, {self.stock_symbol}, {self.price}, {self.quantity}, {self.is_buy}, {datetime.fromtimestamp(self.timestamp).strftime('%Y-%m-%d %H:%M:%S')}, {self.order_id})"
        return f"Order({self.trader_id}, {'Limit' if self.order_type == 0 else 'Market'}, {self.stock_symbol}, {self.price}, {self.quantity}, {self.is_buy}, {self.timestamp}, {self.order_id})"