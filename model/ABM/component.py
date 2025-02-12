import copy

import random
import math
import time
from datetime import datetime

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


class Trader:
    def __init__(self, trader_id, cash, stock_hold=None):
        self.orders = []    #记录属于交易者的订单的order_id
        self.cash = cash
        self.trader_id = trader_id
        # 股票持仓，字典形式存储股票和对应的股数
        self.stock_hold = stock_hold if stock_hold is not None else {}

        self.Theta = 0       # 提交限价订单的概率
        self.Mu = 0          # 提交市价订单的概率
        self.Delta = 0.005   # 限价订单的取消概率

        self.volume = 100    # 每个订单的体积是100，无论限价订单或市价订单

    '''# 用于创建限价订单并预处理资金和库存
    def create_order(self, order_type, stock_symbol, price, quantity, is_buy, create_time):
        # 创建订单为买单，冻结该部分的资金
        if is_buy:
            cost = price * quantity
            self.cash -= cost
            # 创建订单，先不给唯一标识，在交易所中统一赋值
            new_order = Order(self.trader_id, order_type, stock_symbol, price, quantity, is_buy, create_time, order_id=None)
        
        # 创建订单为卖单，冻结该部分的股票
        else:
            self.stock_hold[stock_symbol] -= quantity
            # 创建订单，先不给唯一标识，在交易所中统一赋值
            new_order = Order(self.trader_id, order_type, stock_symbol, price, quantity, is_buy, create_time, order_id=None)

        return new_order

    def cancel_order(self):
        pass

    # 限价订单完成后更新状态
    def update_state_by_limit_order(self, complete_order, complete_quantity, complete_price):
        # 完成订单为买单
        if complete_order.is_buy:
            # 计算花费
            cost = complete_quantity * complete_price
            # 恢复完成部分的冻结资金，并减去花费（订单可能只完成部分，花费不会超过冻结资金）
            self.cash = self.cash + complete_order.price * complete_quantity - cost
            # 更新股票持仓
            if complete_order.stock_symbol in self.stock_hold:
                self.stock_hold[complete_order.stock_symbol] += complete_quantity
            else:
                self.stock_hold[complete_order.stock_symbol] = complete_quantity

        # 完成订单为卖单
        else:
            # 计算收益
            revenue = complete_quantity * complete_price
            self.cash += revenue

        # 如果该订单全部完成，从自己的订单列表中删除完成订单
        if complete_order.quantity == complete_quantity:
            self.orders.remove(complete_order.order_id)'''

    # 订单完成后更新状态(资产清算)
    def update_state(self, complete_order, complete_quantity, complete_price):
        # 完成订单为买单
        if complete_order.is_buy:
            # 计算花费，更新资金
            cost = complete_quantity * complete_price
            self.cash -= cost
            # 更新股票持仓
            self.stock_hold[complete_order.stock_symbol] += complete_quantity

        # 完成订单为卖单
        else:
            # 计算收益，更新资金
            revenue = complete_quantity * complete_price
            self.cash += revenue
            # 更新股票持仓
            self.stock_hold[complete_order.stock_symbol] -= complete_quantity

        # 如果该订单全部完成，并且该订单是限价单，从自己的订单列表中删除完成订单
        if complete_order.order_type == 0:
            if complete_order.quantity == complete_quantity:
                self.orders.remove(complete_order.order_id)

    '''# 获取匹配结果，并更新状态(match_orders:(order, quantity, price))
    def get_match_info_and_update(self, match_orders):
        # 从匹配结果中得到属于自己订单的信息
        for order, quantity, price in match_orders:
            self.update_state(order, quantity, price)'''



# 基本面交易者
class Fundamental_Trader(Trader):
    def __init__(self, trader_id, cash, stock_hold, value, N_FT, S_FT, k1, k2):
        # 调用基类的构造器
        super().__init__(trader_id, cash, stock_hold)
        self.trader_type = "Fundamental_Trader"
        self.fundamental_value = value  # 股票的基本价值向量，从真实数据中得出
        self.price_trend = 0            # 当前市场中心价，在每个模拟的step后更新，用于计算挂单概率
        self.trader_num = N_FT     # 基本面交易者的数量
        self.trading_step = S_FT        # 基本面交易者交易的间隔

        self.k1 = k1     # 线性需求分量的系数，初始值设为1
        self.k2 = k2     # 多项式需求分量的系数，初始值设为1


    # 基本面交易者的交易逻辑，每个交易者在每个step调用一次该函数
    def trading_function(self, stock_symbol, timestamp, simulation_step, price_trend):
        # 基本面交易者只提交市价单，Theta值为0
        self.Theta = 0
        # 更新交易者记录的当前市场价格
        self.price_trend = price_trend
        # 计算提交市价单的概率
        self.Mu = (self.k1 * abs(self.fundamental_value[simulation_step] - self.price_trend) +
                   self.k2 * abs(self.fundamental_value[simulation_step] - self.price_trend) ** 3) / self.trader_num
        # 从U(0, 1)中抽取随机值
        p = random.uniform(0, 1)
        # 挂单结果
        market_orders = []
        # 挂单逻辑
        if simulation_step % self.trading_step == 0 and p < self.Mu:
            # 当前基本面价值大于市场价格，执行一次市价买单
            if self.fundamental_value[simulation_step] - self.price_trend > 0:
                order = Order(self.trader_id, 1, stock_symbol, None, self.volume, True, timestamp)
                market_orders.append(order)
            # 当前基本面价值小于市场价格，执行一次市价卖单
            elif self.fundamental_value[simulation_step] - self.price_trend < 0:
                order = Order(self.trader_id, 1, stock_symbol, None, self.volume, False, timestamp)
                market_orders.append(order)

        return market_orders


# 动量交易者(长期和短期)
class Momentum_Trader(Trader):
    def __init__(self, trader_id, cash, stock_hold, N_MT, Alpha, Beta, Gamma, open_price_trend):
        # 调用基类的构造器
        super().__init__(trader_id, cash, stock_hold)
        self.trader_type = "Momentum_Trader"    # 创建时修改为对应类型
        self.trader_num = N_MT  # 动量交易者数量，长期和短期分开算
        self.Mt = 0             # 趋势信号，过去回报的指数加权移动平均值(初始值为真实价格的第一次回报)
        self.Alpha = Alpha      # 衰减率，固定值，长期动量交易者：Alpha = 0.001  短期动量交易者：Alpha = 0.9
        self.Beta = Beta        # 需求系数，需要学习的参数，长期和短期不一样，为正值
        self.Gamma = Gamma      # 需求计算系数

        self.Delta = 0.005  # 限价订单的取消概率
        self.Rho = 0.2      # 提交市价订单的概率与提交限价订单的概率之比

        # 改正：开始时应该用开盘价初始化记录的行情价格
        self.last_price_trend = open_price_trend   # 上一次的市场价格，初始值设为开盘价
        self.price_trend = open_price_trend        # 当前市场价格，初始值设为开盘价
        # self.last_price_trend = 0   # 上一次的市场价格，初始值设为0
        # self.price_trend = 0        # 当前市场价格，初始值设为0

    def trading_function(self, stock_symbol, timestamp, price_trend, price_distance):
        # 更新上一次市场价格和当前市场价格
        self.last_price_trend = self.price_trend
        self.price_trend = price_trend

        # 返回值，提交的订单和撤销的订单
        cancel_orders = []
        market_orders = []
        limit_orders = []

        # 遍历当前拥有的限价订单，按一定概率撤销订单
        for order_id in self.orders:
            # 从U(0, 1)中抽取随机值，当随机值小于限价订单的取消概率时撤销订单
            if random.uniform(0, 1) < self.Delta:
                cancel_orders.append(order_id)
                self.orders.remove(order_id)

        # 计算趋势信号
        self.Mt = (1 - self.Alpha) * self.Mt + self.Alpha * (self.price_trend - self.last_price_trend)
        # 计算提交限价订单的概率
        self.Theta = (self.Beta * math.tanh(self.Gamma * self.Mt)) / self.trader_num
        # 计算提交市价订单的概率
        self.Mu = self.Theta * self.Rho

        # 挂单逻辑(限价订单，买单低于市场中价，卖单高于市场中价)
        if random.uniform(0, 1) < self.Theta:
            if self.Mt > 0:
                # 计算价格，挂限价买单
                price = round(price_trend - price_distance, 2)
                order = Order(self.trader_id, 0, stock_symbol, price, self.volume, True, timestamp)
                limit_orders.append(order)
            elif self.Mt < 0:
                # 计算价格，挂限价卖单
                price = round(price_trend + price_distance, 2)
                order = Order(self.trader_id, 0, stock_symbol, price, self.volume, False, timestamp)
                limit_orders.append(order)

        # 挂单逻辑(市价订单)
        if random.uniform(0, 1) < self.Mu:
            if self.Mt > 0:
                # 挂市价买单
                order = Order(self.trader_id, 1, stock_symbol, None, self.volume, True, timestamp)
                market_orders.append(order)
            elif self.Mt < 0:
                # 挂市价卖单
                order = Order(self.trader_id, 1, stock_symbol, None, self.volume, False, timestamp)
                market_orders.append(order)

        return cancel_orders, market_orders, limit_orders


# 噪音交易者
class Noise_Trader(Trader):
    def __init__(self, trader_id, cash, stock_hold, N_NT, Delta_NT):
        # 调用基类的构造器
        super().__init__(trader_id, cash, stock_hold)
        self.trader_type = "Noise_Trader"
        self.trader_num = N_NT      # 噪音交易者的数量
        self.Delta_NT = Delta_NT    # 控制噪音交易者总需求水平的参数，需要损失函数更新
        self.price_trend = 0        # 当前市场行情，在每个模拟的step后更新，用于计算挂单概率

        self.Delta = 0.005          # 限价订单的取消概率
        self.Rho = 0.2              # 提交市价订单的概率与提交限价订单的概率之比

        self.Theta = self.Delta_NT / self.trader_num    # 提交限价订单的概率，模拟过程中保持不变
        self.Mu = self.Theta * self.Rho     # 提交市价订单的概率，模拟过程中保持不变

    def trading_function(self, stock_symbol, timestamp, price_trend, price_distance):
        # 更新市场价格
        self.price_trend = price_trend

        # 返回值，提交的订单和撤销的订单
        cancel_orders = []
        market_orders = []
        limit_orders = []

        # 遍历当前拥有的限价订单，按一定概率撤销订单
        for order_id in self.orders:
            # 从U(0, 1)中抽取随机值，当随机值小于限价订单的取消概率时撤销订单
            if random.uniform(0, 1) < self.Delta:
                cancel_orders.append(order_id)
                self.orders.remove(order_id)

        # 挂单逻辑(限价订单，买单低于市场中价，卖单高于市场中价)
        if random.uniform(0, 1) < self.Theta:
            p = random.uniform(0, 1)
            if p < 0.5:
                # 计算价格，挂限价买单
                price = round(price_trend - price_distance, 2)
                order = Order(self.trader_id, 0, stock_symbol, price, self.volume, True, timestamp)
                limit_orders.append(order)
            elif p > 0.5:
                # 计算价格，挂限价卖单
                price = round(price_trend + price_distance, 2)
                order = Order(self.trader_id, 0, stock_symbol, price, self.volume, False, timestamp)
                limit_orders.append(order)

        # 挂单逻辑(市价订单)
        if random.uniform(0, 1) < self.Mu:
            p = random.uniform(0, 1)
            if p < 0.5:
                # 挂市价买单
                order = Order(self.trader_id, 1, stock_symbol, None, self.volume, True, timestamp)
                market_orders.append(order)
            elif p > 0.5:
                # 挂市价卖单
                order = Order(self.trader_id, 1, stock_symbol, None, self.volume, False, timestamp)
                market_orders.append(order)

        return cancel_orders, market_orders, limit_orders


# 做市商
'''class Market_Maker(Trader):
    def __init__(self, trader_id, cash, stock_hold, Theta_MM, Delta_MM):
        # 调用基类的构造器
        super().__init__(trader_id, cash, stock_hold)
        self.trader_type = "Market_Maker"
        self.Theta = Theta_MM   # 提交报价的概率（一个报价包括一个限价买单和一个限价卖单）
        self.Delta = Delta_MM   # 取消报价的概率
        self.Mu = 0             # 正常交易时间内只提交限价订单

        self.p_edge_MM = 4      # 限价订单价格距离从均匀分布U(0, p_edge_MM)中采样

        # 如果库存达到头寸限制，做市商会积极减少库存直到安全头寸水平
        self.Epsilon_limit_MM = 5000    # 做市商的头寸限制
        self.Epsilon_safe_MM = 101      # 做市商的安全头寸水平
        self.Flag = 0                   # 库存进入不同状态的标志

        self.Epsilon_rest_MM = 12000    # 暂停交易的时间长度
        self.Restart_step = 0           # 重启交易的时间位置

    def trading_function(self, stock_symbol, timestamp, simulation_step, price_trend):
        # 返回值，提交的订单和撤销的订单
        cancel_orders = []
        market_orders = []
        limit_orders = []

        # 如果库存超过头寸限制，进入压力交易阶段
        if self.stock_hold[stock_symbol] >= self.Epsilon_limit_MM:
            self.Flag = 1
            self.Restart_step = simulation_step + self.Epsilon_rest_MM

        # 如果库存回到安全水平，进入正常交易阶段
        if self.Flag == 1 and self.stock_hold[stock_symbol] <= self.Epsilon_safe_MM:
            self.Flag = 0
        
        # 压力交易阶段，清空所有限价订单
        if self.Flag == 1:
            cancel_orders.extend(self.orders)
            self.orders.clear()
            # 如果库存小于0，需要市价买单补充库存，否则用市价卖单清空库存
            if self.stock_hold[stock_symbol] < 0:
                # 挂市价买单
                order = Order(self.trader_id, 1, stock_symbol, None, self.volume, True, timestamp)
                market_orders.append(order)
            else:
                # 挂市价卖单
                order = Order(self.trader_id, 1, stock_symbol, None, self.volume, False, timestamp)
                market_orders.append(order)

        # 超过停止交易时间，进入正常交易阶段
        elif simulation_step > self.Restart_step:
            # 按一定概率撤销全部订单
            if random.uniform(0, 1) < self.Delta:
                cancel_orders.extend(self.orders)
                self.orders.clear()
            # 按一定概率提交报价，一个报价包括一个限价买单和一个限价卖单
            if random.uniform(0, 1) < self.Theta:
                # 限价订单价格距离从均匀分布U(0, p_edge_MM)中采样
                price_distance = random.uniform(0, self.p_edge_MM)
                buy_limit_order = Order(self.trader_id, 0, stock_symbol, price_trend - price_distance, self.volume, True, timestamp)
                sell_limit_order = Order(self.trader_id, 0, stock_symbol, price_trend + price_distance, self.volume, False, timestamp)
                limit_orders.append(buy_limit_order)
                limit_orders.append(sell_limit_order)
            
        return cancel_orders, market_orders, limit_orders

    # 做市商更新库存的函数
    def update_position(self):
        pass'''


class Exchange:

    def __init__(self):
        self.orders = []  # 所有订单的列表
        self.order_id = 1   # 订单的全局唯一标识，初始值为1

    def add_order(self, order):
        # 给订单标识赋值
        order.order_id = self.order_id
        self.order_id += 1

        self.orders.append(order)
        # 订单排序
        self.orders.sort(key=lambda x: (
            not x.is_buy,   # 买单在前，卖单在后
            -x.price if x.is_buy else x.price,  # 买单按价格降序，卖单按价格升序
            x.timestamp   # 相同价格的订单按时间戳升序
        ), reverse=False)

        # 把订单标识返回给交易者
        return order.order_id

    # 通过标识查找订单
    def find_order(self, order_id):
        order = [o for o in self.orders if o.order_id == order_id]
        return order[0]

    # 通过标识删除订单
    def del_order(self, order_id):
        order = [o for o in self.orders if o.order_id == order_id]
        # 如果找到了订单，删除该订单
        if len(order) > 0:
            self.orders.remove(order[0])

    # 计算中心价
    def calculate_midprice(self):
        buy_orders = [o for o in self.orders if o.is_buy]
        sell_orders = [o for o in self.orders if not o.is_buy]

        # 如果订单簿中数据不足以计算中心价，返回None
        if len(buy_orders) == 0 or len(sell_orders) == 0:
            return None

        buy = buy_orders[0]     # 取最高价买单
        sell = sell_orders[0]   # 取最低价卖单
        mid_price = round((buy.price + sell.price) / 2, 2)

        return mid_price


    # 撮合市价订单（及时成交剩余撤销）
    def add_and_match_market_order(self, order):
        # 如果是限价单,报错
        if order.order_type == 0:
            print("错误，该订单不是市价单")
            return None
        else:
            matched_orders = []

            # 如果市价单为买单
            if order.is_buy:
                sell_orders = [o for o in self.orders if not o.is_buy]
                while order.quantity > 0 and sell_orders:
                    sell = sell_orders[0]
                    quantity = min(order.quantity, sell.quantity)
                    # 创建新的订单实例来记录成交信息
                    matched_buy = Order(order.trader_id, order.order_type, order.stock_symbol, order.price, order.quantity, order.is_buy, order.timestamp, order.order_id)
                    matched_sell = Order(sell.trader_id, sell.order_type, sell.stock_symbol, sell.price, sell.quantity, sell.is_buy, sell.timestamp, sell.order_id)
                    matched_orders.append((matched_buy, matched_sell, quantity, sell.price))
                    # 更新交易后订单信息，如果订单数量为0，清空该订单
                    order.quantity -= quantity
                    sell.quantity -= quantity

                    if sell.quantity == 0:
                        sell_orders.pop(0)
                        self.orders.pop(self.orders.index(sell))

            else:
                buy_orders = [o for o in self.orders if o.is_buy]
                while order.quantity > 0 and buy_orders:
                    buy = buy_orders[0]
                    quantity = min(order.quantity, buy.quantity)
                    # 创建新的订单实例来记录成交信息
                    matched_buy = Order(buy.trader_id, buy.order_type, buy.stock_symbol, buy.price, buy.quantity, buy.is_buy, buy.timestamp, buy.order_id)
                    matched_sell = Order(order.trader_id, order.order_type, order.stock_symbol, order.price, order.quantity, order.is_buy, order.timestamp, order.order_id)
                    matched_orders.append((matched_buy, matched_sell, quantity, buy.price))
                    # 更新交易后订单信息，如果订单数量为0，清空该订单
                    order.quantity -= quantity
                    buy.quantity -= quantity

                    if buy.quantity == 0:
                        buy_orders.pop(0)
                        self.orders.pop(self.orders.index(buy))

            return matched_orders

    # 匹配订单, 计算价格 (集合竞价)
    def match_orders_in_call_auction(self):
        matched_orders = []
        buy_orders = [o for o in self.orders if o.is_buy]
        sell_orders = [o for o in self.orders if not o.is_buy]
        while buy_orders and sell_orders:
            buy = buy_orders[0]     # 取最高价买单
            sell = sell_orders[0]   # 取最低价卖单
            if buy.price >= sell.price:
                # 计算成交的货品数量
                quantity = min(buy.quantity, sell.quantity)
                # 创建新的订单实例来记录成交信息
                matched_buy = Order(buy.trader_id, buy.order_type, buy.stock_symbol, buy.price, buy.quantity, buy.is_buy, buy.timestamp, buy.order_id)
                matched_sell = Order(sell.trader_id, sell.order_type, sell.stock_symbol, sell.price, sell.quantity, sell.is_buy, sell.timestamp, sell.order_id)
                matched_orders.append((matched_buy, matched_sell, quantity))
                # 更新交易后订单信息，如果订单数量为0，清空该订单
                buy.quantity -= quantity
                sell.quantity -= quantity

                if buy.quantity == 0:
                    buy_orders.pop(0)
                    self.orders.pop(self.orders.index(buy))

                if sell.quantity == 0:
                    sell_orders.pop(0)
                    self.orders.pop(self.orders.index(sell))

            else:
                break
        # 计算集合竞价市场价格（最后一笔成交价）
        if len(matched_orders) > 0:
            mean_price = round((matched_orders[-1][0].price + matched_orders[-1][1].price) / 2, 2)
        else:
            mean_price = None

        # 将市场价格补充到每个match_order末尾，对齐元组大小
        new_matched_orders = [o + (mean_price,) for o in matched_orders]

        return new_matched_orders, mean_price

    # 匹配订单, 计算价格 (连续竞价)
    def match_orders_in_continuous_auction(self):
        matched_orders = []
        buy_orders = [o for o in self.orders if o.is_buy]
        sell_orders = [o for o in self.orders if not o.is_buy]
        while buy_orders and sell_orders:
            buy = buy_orders[0]     # 取最高价买单
            sell = sell_orders[0]   # 取最低价卖单
            if buy.price >= sell.price:
                # 计算成交的货品数量
                quantity = min(buy.quantity, sell.quantity)
                # 计算成交价格
                mean_price = round((buy.price + sell.price) / 2, 2) #保留两位小数
                # 创建新的订单实例来记录成交信息
                matched_buy = Order(buy.trader_id, buy.order_type, buy.stock_symbol, buy.price, buy.quantity, buy.is_buy, buy.timestamp, buy.order_id)
                matched_sell = Order(sell.trader_id, sell.order_type, sell.stock_symbol, sell.price, sell.quantity, sell.is_buy, sell.timestamp, sell.order_id)
                matched_orders.append((matched_buy, matched_sell, quantity, mean_price))
                # 更新交易后订单信息，如果订单数量为0，清空该订单
                buy.quantity -= quantity
                sell.quantity -= quantity

                if buy.quantity == 0:
                    buy_orders.pop(0)
                    self.orders.pop(self.orders.index(buy))

                if sell.quantity == 0:
                    sell_orders.pop(0)
                    self.orders.pop(self.orders.index(sell))

            else:
                break

        return matched_orders


    # ----------- 处理当前交易所订单簿为市场行情 --------------
    def order_book_to_market(self, mid_price, range_num, price_range):
        """
        :param mid_price: 当前的市场中心价
        :param range_num: 行情档位数量
        :param price_range: 行情档位之间的价格间隔
        :return: 当前市场行情
        """
        # 将订单簿划分成卖单和卖单（交易所当前时刻的订单簿是有序的，买单按价格降序，卖单按价格升序）
        buy_orders = [o for o in self.orders if o.is_buy]
        sell_orders = [o for o in self.orders if not o.is_buy]

        # 计算买卖的档位价格（买价格从中心价递减，卖价格从中心价递增）
        buy_prices = [mid_price - price_range * (i + 1) for i in range(range_num)]
        buy_prices = [round(price, 2) for price in buy_prices]
        sell_prices = [mid_price + price_range * (i + 1) for i in range(range_num)]
        sell_prices = [round(price, 2) for price in sell_prices]


        # -------统计买方档位价格对应的存量-------
        buy_volumes = []
        range_count = 0
        volume = 0
        for order in buy_orders:
            if order.price >= buy_prices[range_count]:
                volume += order.quantity
            # 进入下一档，保存上一档数据，重置存量
            else:
                buy_volumes.append(volume)
                volume = 0
                range_count += 1
                # 最后一档，其余订单不统计
                if range_count >= range_num:
                    break
        # 不足五档，存量补0
        if len(buy_volumes) < range_num:
            for i in range(len(buy_volumes), range_num):
                buy_volumes.append(0)

        # ------统计卖方档位价格对应的存量---------
        sell_volumes = []
        range_count = 0
        volume = 0
        for order in sell_orders:
            if order.price <= sell_prices[range_count]:
                volume += order.quantity
            # 进入下一档，保存上一档数据，重置存量
            else:
                sell_volumes.append(volume)
                volume = 0
                range_count += 1
                # 最后一档，其余订单不统计
                if range_count >= range_num:
                    break
        # 不足五档，存量补0
        if len(sell_volumes) < range_num:
            for i in range(len(sell_volumes), range_num):
                sell_volumes.append(0)

        # 将档位价格和存量集中成当前市场行情(buy1,sell1,bc1,sc1...)
        market_situations = []
        for i in range(range_num):
            market_situations.append(buy_prices[i])
            market_situations.append(sell_prices[i])
            market_situations.append(buy_volumes[i])
            market_situations.append(sell_volumes[i])

        return market_situations

# Example:
'''exchange = Exchange()
exchange.add_order(Order(1, '0001', 3.80, 2, True, 1))
exchange.add_order(Order(1, '0001', 3.76, 6, True, 2))
exchange.add_order(Order(1, '0001', 3.60, 7, True, 4))
exchange.add_order(Order(2, '0001', 3.52, 5, False, 1))
exchange.add_order(Order(2, '0001', 3.57, 1, False, 3))
exchange.add_order(Order(3, '0001', 3.54, 6, False, 3))
exchange.add_order(Order(1, '0001', 3.60, 2, True, 3))
exchange.add_order(Order(2, '0001', 3.70, 6, False, 2))
exchange.add_order(Order(3, '0001', 3.75, 3, False, 4))
exchange.add_order(Order(1, '0001', 3.65, 4, True, 3))

for order in exchange.orders:
    print(order)

# match_orders, mean_price = exchange.match_orders_in_call_auction()
match_orders = exchange.match_orders_in_continuous_auction()
for order in match_orders:
    print(order)
    print(order[3])
# print("-----------")
# print("集合竞价平均价格：",mean_price)'''



