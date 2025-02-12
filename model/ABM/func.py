from pykalman import KalmanFilter
from model.ABM.component import Fundamental_Trader, Momentum_Trader, Noise_Trader,Market, Exchange
import numpy as np
# -------------计算基本面价值---------------
def calculate_fundamental_value(prices):
    # 初始化卡尔曼滤波器
    kf = KalmanFilter(
        transition_matrices=[[1]],      # 状态转移矩阵，1x1 矩阵
        observation_matrices=[[1]],     # 观测矩阵，1x1 矩阵
        transition_covariance=0.0001,   # 过程噪声协方差，1x1 矩阵
        observation_covariance=2.0,     # 观测噪声协方差，1x1 矩阵
        initial_state_mean=prices[0]    # 初始状态均值，使用价格序列的第一个值
    )

    # 使用卡尔曼滤波器
    smoothed_state_means, smoothed_state_covariances = kf.smooth(prices)

    # 提取基本面价值，保留两位小数
    fundamental_value = []
    for mean in smoothed_state_means:
        fundamental_value.append(round(mean[0], 2))

    return fundamental_value

# --------交易者、交易所、市场实例创建-------
def create_instance(config, fundamental_value, open_prices):

    # 创建交易者实例
    traders = []
    trader_id = 0   # 交易者标识，唯一，与traders索引对齐
    cash = 100000   # 本次模拟不限制现金
    stock_hold = {config["STOCK_SYMBOL"] : 0}

    # 创建基本面交易者
    for i in range(0, config["N_FT"]):
        trader = Fundamental_Trader(trader_id, cash, stock_hold, fundamental_value, config["N_FT"], config["S_FT"], config["K1"], config["K2"])
        trader_id += 1
        traders.append(trader)

    # 创建长期动量交易者
    for i in range(0, config["N_LMT"]):
        trader = Momentum_Trader(trader_id, cash, stock_hold, config["N_LMT"], config["ALPHA_L"], config["BETA_L"], config["GAMMA"], open_prices)
        trader.Rho = config["RHO"]
        trader.Delta = config["DELTA"]
        trader.trader_type = "Long_term_Momentum_Trader"
        trader_id += 1
        traders.append(trader)

    # 创建短期动量交易者
    for i in range(0, config["N_SMT"]):
        trader = Momentum_Trader(trader_id, cash, stock_hold, config["N_SMT"], config["ALPHA_S"], config["BETA_S"], config["GAMMA"], open_prices)
        trader.Rho = config["RHO"]
        trader.Delta = config["DELTA"]
        trader.trader_type = "Short_term_Momentum_Trader"
        trader_id += 1
        traders.append(trader)

        # 创建噪声交易者
    for i in range(0, config["N_NT"]):
        trader = Noise_Trader(trader_id, cash, stock_hold, config["N_NT"], config["DELTA_NT"])
        trader.Rho = config["RHO"]
        trader.Delta = config["DELTA"]
        trader_id += 1
        traders.append(trader)

    # 创建交易所和市场
    exchange = Exchange()
    market = Market()

    return traders, exchange, market

# -------------市场一轮模拟-----------------
def simulate_market(traders, exchange, market, prices, dates, trader_type, config):
    # 设置初始时间戳
    timestamp = dates[0]

    # 用于收集每步模拟中的所有匹配结果（传入市场后清空）
    all_match_result = []

    # 添加开盘市场信息
    open_price = round(prices[0], 2)    # 用真实数据中的开盘价
    open_mid_price = round(prices[0], 2)      # 用真实数据作为中心价
    open_market = exchange.order_book_to_market(open_mid_price, 10, 0.01)
    market.update_simulation(exchange.orders, all_match_result, open_price, open_mid_price, open_market, timestamp)

    # 记录模拟步数
    simulation_step = 0 # 每步模拟结束后加1(使市场价格与基本面价值对齐)

    # 模拟过程
    while simulation_step < len(dates) - 1:
        timestamp = dates[simulation_step + 1]

        # 收集所有当前时刻产生的限价订单、市价订单和要取消的订单
        all_limit_orders = []
        all_market_orders = []
        all_cancel_orders = []

        all_match_result = []

        # 对于每一个trader，执行对应的交易逻辑
        for trader in traders:
            # 收集最新市场信息，更新自身状态
            current_price = market.price_trend[-1][1]
            match_result = market.match_result[-1][1]
            current_mid_price = market.mid_price[-1][1]

            # match_order: (buy, sell, quantity, price)
            for match_order in match_result:
                # 如果买单属于自己，更新自身状态
                if trader.trader_id == match_order[0].trader_id:
                    trader.update_state(match_order[0], match_order[2], match_order[3])
                # 如果卖单属于自己，更新自身状态
                if trader.trader_id == match_order[1].trader_id:
                    trader.update_state(match_order[1], match_order[2], match_order[3])

            # 如果是基本面交易者，执行基本面交易逻辑
            if trader.trader_type == trader_type[0]:
                market_orders = trader.trading_function(config["STOCK_SYMBOL"], timestamp, simulation_step, current_mid_price)
                all_market_orders.extend(market_orders)

            # 如果是长期动量交易者，执行长期动量交易逻辑
            if trader.trader_type == trader_type[1]:
                # 从标准正态分布中随机抽样
                sample = np.random.randn()
                # 根据对数正态分布的均值和标准差将样本转换为对数正态分布的样本作为价格距离
                price_distance = np.exp(config["MU_L"] + config["SIGMA_L"] * sample)

                cancel_orders, market_orders, limit_orders = trader.trading_function(config["STOCK_SYMBOL"], timestamp, current_mid_price, price_distance)
                all_cancel_orders.extend(cancel_orders)
                all_market_orders.extend(market_orders)
                all_limit_orders.extend(limit_orders)
                # print("长期动量挂单概率", trader.Theta)

            # 如果是短期动量交易者，执行短期动量交易逻辑
            if trader.trader_type == trader_type[2]:
                # 从标准正态分布中随机抽样
                sample = np.random.randn()
                # 根据对数正态分布的均值和标准差将样本转换为对数正态分布的样本作为价格距离
                price_distance = np.exp(config["MU_L"] + config["SIGMA_L"] * sample)

                cancel_orders, market_orders, limit_orders = trader.trading_function(config["STOCK_SYMBOL"], timestamp, current_mid_price, price_distance)
                all_cancel_orders.extend(cancel_orders)
                all_market_orders.extend(market_orders)
                all_limit_orders.extend(limit_orders)

            # 如果是噪声交易者，执行噪声交易逻辑
            if trader.trader_type == trader_type[3]:
                # 从标准正态分布中随机抽样
                sample = np.random.randn()
                # 根据对数正态分布的均值和标准差将样本转换为对数正态分布的样本作为价格距离
                price_distance = np.exp(config["MU_L"] + config["SIGMA_L"] * sample)

                cancel_orders, market_orders, limit_orders = trader.trading_function(config["STOCK_SYMBOL"], timestamp, current_mid_price, price_distance)
                all_cancel_orders.extend(cancel_orders)
                all_market_orders.extend(market_orders)
                all_limit_orders.extend(limit_orders)


        # 所有交易者执行完交易逻辑后，按取消订单、市价单、限价单顺序更新订单簿和完成订单撮合
        # 先完成订单取消
        for cancel_order_id in all_cancel_orders:
            exchange.del_order(cancel_order_id)

        # 接着进行市价单的撮合，返回交易结果
        for market_order in all_market_orders:
            market_matched_orders = exchange.add_and_match_market_order(market_order)
            all_match_result.extend(market_matched_orders)

        # 最后将限价单加入订单簿，把order_id返回给交易者保存
        for limit_order in all_limit_orders:
            limit_order_id = exchange.add_order(limit_order)
            traders[limit_order.trader_id].orders.append(limit_order_id)

        # 统一做集合竞价
        limit_matched_orders, mean_price = exchange.match_orders_in_call_auction()
        # 如果集合竞价没有成交结果，市场价格取所有市价单成交价格的均值
        if mean_price == None:
            # 如果没有市价单成交结果，市场价格为上一个时刻的市场价格
            if len(all_match_result) == 0:
                mean_price = current_price
            else:
                price_sum = 0
                for m in all_match_result:
                    price_sum += m[3]
                mean_price = round(price_sum / len(all_match_result), 2)

        all_match_result.extend(limit_matched_orders)

        # 计算当前时刻中心价
        mid_price = exchange.calculate_midprice()
        if mid_price == None:
            mid_price = current_mid_price

        # 打印进度
        '''if simulation_step % 100 == 0:
            print("simulation step: ", simulation_step)       
            print("取消订单：", all_cancel_orders)
            print("市价单：", all_market_orders)
            print("限价单", all_limit_orders)
            print("订单簿：", exchange.orders)
            print("匹配结果:", all_match_result)
            print("市场价格：", mean_price)
            print("市场中心价：", mid_price)'''

        # --- 补充：计算当前多档行情（每档价格间隔为0.01） ------
        multiple_market = exchange.order_book_to_market(mid_price, 10, 0.01)

        '''# 将最终的订单簿状态，交易匹配结果和市场价格存入市场
        market.update_simulation(exchange.orders, all_match_result, mean_price, mid_price, timestamp)'''

        # 将最终的订单簿状态，交易匹配结果、市场价格和多档行情存入市场
        market.update_simulation(exchange.orders, all_match_result, mean_price, mid_price, multiple_market, timestamp)

        # 当前simulation step已完成，模拟步数加1
        simulation_step += 1

    # 从市场中获得中心价
    mid_price = []
    for price in market.mid_price:
        mid_price.append(price[1])

    # ------补充：从市场中获得多档行情-------
    multiple_market = []
    for multiple in market.multiple_market:
        multiple_market.append(multiple[1])

    return mid_price, multiple_market, market