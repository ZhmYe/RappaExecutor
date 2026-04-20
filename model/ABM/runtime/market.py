from order import Order
import copy

class Market:
    def __init__(self):
        self.orders = []
        self.match_result = []
        self.price_trend = []
        self.mid_price = []
        self.multiple_market = []   # 保存多档行情

    '''# 更新开盘市场信息
    def update_open(self, orders, match_orders, mean_price, current_time):
        self.orders.append([current_time, orders])
        self.match_result.append([current_time, match_orders])
        # 保存市场行情
        self.price_trend.append([current_time, mean_price])

    # 更新开盘后持续变化的市场信息
    def update_continuous(self, orders, match_orders, current_time):
        self.orders.append([current_time, orders])
        self.match_result.append([current_time, match_orders])
        # 保存市场行情
        #for order in match_orders:
            # 使用后来的订单的时间
        #    price_time = max(order[0].timestamp, order[1].timestamp)
        #    self.price_trend.append([price_time, order[3]])

        # 简化处理
        if len(match_orders):
            price_time = max(match_orders[-1][0].timestamp, match_orders[-1][1].timestamp)
            self.price_trend.append([price_time, match_orders[-1][3]])'''

    # 更新模拟中每步的市场信息
    def update_simulation(self, orders, match_orders, mean_price, mid_price, multiple_market, current_time):
        # 保存当前时刻的订单簿
        self.orders.append([current_time, copy.deepcopy(orders)])
        # self.orders.append([current_time, orders])
        # 保存当前时刻的所有订单匹配结果
        self.match_result.append([current_time, match_orders])
        # 保存当前时刻的市场行情
        self.price_trend.append([current_time, mean_price])
        # 保存当前时刻的市场中心价
        self.mid_price.append([current_time, mid_price])
        # 保存当前时刻的多档行情
        self.multiple_market.append([current_time, multiple_market])

