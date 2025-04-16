from model.ABM_.exchange import Exchange
from model.ABM_.trader import Fundamental_Trader, Momentum_Trader, Noise_Trader
from model.ABM_.market import Market

# from loss_function import loss_function

import numpy as np
from pykalman import KalmanFilter
import os
import csv

#-----------导入初始参数到字典中------------
def init_config(config):
    params_config = {

        # 前六个为需要更新的参数
        "MU_L": config.MU_L,
        "DELTA_NT": config.DELTA_NT,
        "K1": config.K1,
        "K2": config.K2,
        "BETA_L": config.BETA_L,
        "BETA_S": config.BETA_S,

        # 所有模型共同需要的参数
        "THETA": config.THETA,
        "MU": config.MU,
        "DELTA": config.DELTA,
        "RHO": config.RHO,
        "VOLUME": config.VOLUME,
        "SIGMA_L": config.SIGMA_L,

        # 基本面交易者的固定参数
        "N_FT": config.N_FT,
        "S_FT": config.S_FT,

        # 动量交易者
        "GAMMA": config.GAMMA,
        "N_LMT": config.N_LMT,
        "ALPHA_L": config.ALPHA_L,
        "N_SMT": config.N_SMT,
        "ALPHA_S": config.ALPHA_S,

        # 噪音交易者
        "N_NT": config.N_NT,

        # 股票类型
        "STOCK_SYMBOL": config.STOCK_SYMBOL
    }

    return params_config


# -------使用价格序列计算日收盘价序列--------
def calculate_daily_price(prices, freq):
    # 每日包含的时间点
    period = int(240 / freq)
    # 总天数
    day_num = int(len(prices) / period)
    # 取每日时间片的最后一个时间点的价格
    daily_prices = [prices[period * i + (period - 1)] for i in range(0, day_num)]

    return daily_prices


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
def simulate_market(traders, exchange, market, open, dates, trader_type, config, num_samples):
    # 设置初始时间戳
    timestamp = dates[0]

    # 用于收集每步模拟中的所有匹配结果（传入市场后清空）
    all_match_result = []

    # 添加开盘市场信息
    open_price = open    # 用真实数据中的开盘价
    open_mid_price = open      # 用真实数据作为中心价
    open_market = exchange.order_book_to_market(open_mid_price, 10, 0.01)
    market.update_simulation(exchange.orders, all_match_result, open_price, open_mid_price, open_market, timestamp)

    # 记录模拟步数
    simulation_step = 0 # 每步模拟结束后加1(使市场价格与基本面价值对齐)

    # 模拟过程
    while simulation_step < len(dates) - 1 and simulation_step < num_samples - 1:
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


# ----------从市场模拟数据中获取合成数据并保存----------
def save_synthetic_data(market, target_folder):
    # 确保目标文件夹存在，如果不存在则创建
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)
        print(f"创建目标文件夹: {target_folder}")

    # 从市场中获取中心价时间序列并保存到文件中
    filename = os.path.join(target_folder, 'mid_price.csv')

    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Timestamp', 'Price'])
        # 遍历二维列表并写入数据
        for price in market.mid_price:
            writer.writerow([price[0], price[1]])

    print(f'数据已写入 {filename}')

    # 从市场中获取订单簿时间序列
    filename = os.path.join(target_folder, 'order_book.csv')
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Timestamp', 'OrderBook'])
        # 遍历二维列表并写入数据
        for order in market.orders:
            writer.writerow([order[0], order[1]])

    print(f'数据已写入 {filename}')

    # 从市场中获取逐笔成交数据时间序列
    filename = os.path.join(target_folder, 'match_result.csv')
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Timestamp', 'MatchResult'])
        # 遍历二维列表并写入数据
        for match in market.match_result:
            writer.writerow([match[0], match[1]])

    print(f'数据已写入 {filename}')




# ----------使用数值近似法计算梯度-------------
'''def compute_loss_gradients(true_prices, loss, params_index, config, fundamental_value, dates, trader_type, cof_hill, cof_vol, cof_acf, cof_square_acf, true_markets, freq):

    # 计算日收盘价序列
    daily_true_prices = calculate_daily_price(true_prices, freq)

    # 参数在四位小数的精度上扰动
    epsilon = 0.001

    # 梯度用字典存储
    gradients = {}

    # 遍历每个模型参数
    for index in params_index:
        # 复制当前参数字典，以避免修改原始参数
        config_eps = config.copy()
        # 对当前参数增加一个很小的epsilon值
        config_eps[index] += epsilon

        # 使用修改后的参数值创建实例并计算模拟价格
        traders, exchange, market = create_instance(config_eps, fundamental_value, true_prices[0])
        simulated_prices_eps, simulated_markets_eps = simulate_market(traders, exchange, market, true_prices[0], dates, trader_type, config_eps)

        # 计算修改后计算出的模拟价格对应的日收盘价序列
        daily_simulated_prices_eps = calculate_daily_price(simulated_prices_eps, freq)

        # 计算使用修改后的参数得到的损失
        loss_eps = loss_function(true_prices, simulated_prices_eps, daily_true_prices, daily_simulated_prices_eps, cof_hill, cof_vol, cof_acf, cof_square_acf, true_markets, simulated_markets_eps)

        # 使用中心差分公式计算当前参数的梯度
        # (损失在params_eps时的值 - 原始损失) / epsilon
        gradients[index] = (loss_eps - loss) / epsilon

    return gradients'''


