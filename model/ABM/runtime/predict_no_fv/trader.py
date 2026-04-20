from order import Order
import random
import math

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
        # 计算提交市价单的概率（数值保护：防止极端偏差导致立方项溢出）
        deviation = float(self.fundamental_value[simulation_step] - self.price_trend)
        deviation_abs = min(abs(deviation), 100.0)
        mu_raw = (self.k1 * deviation_abs + self.k2 * (deviation_abs ** 3)) / self.trader_num
        # 概率裁剪到 [0, 1]
        self.Mu = min(1.0, max(0.0, float(mu_raw)))
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
        # 计算提交限价订单的概率(需求量要保证为正数)
        self.Theta = abs(self.Beta * math.tanh(self.Gamma * self.Mt)) / self.trader_num
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





