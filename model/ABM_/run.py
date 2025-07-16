import os
import csv
import pickle
import pandas as pd
from simulate_function import calculate_fundamental_value
from simulate_function import create_instance, simulate_market


def load_params(file_path):
    # 读取 .tsf 文件
    with open(file_path, 'rb') as f:
        params = pickle.load(f)
    return params

'''def load_data(file_path):
    df = pd.read_csv(file_path)
    # 获取"date"、"close"列的数据，并将其转换为列表
    prices = df['close'].tolist()
    dates = df['date'].tolist()
    # 使用卡尔曼滤波计算基本面价值
    fundamental_value = calculate_fundamental_value(prices)
    return prices, dates, fundamental_value'''

# 保存任意数据条目
def save_samples(market, save_num, target_folder):
    # 确保目标文件夹存在，如果不存在则创建
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)
        print(f"创建目标文件夹: {target_folder}")

    folder1 = os.path.join(target_folder, 'mid_price')
    folder2 = os.path.join(target_folder, 'order_book')
    folder3 = os.path.join(target_folder, 'match_result')
    
    if not os.path.exists(folder1):
        os.makedirs(folder1)
        print(f"创建目标文件夹: {folder1}")

    if not os.path.exists(folder2):
        os.makedirs(folder2)
        print(f"创建目标文件夹: {folder2}")

    if not os.path.exists(folder3):
        os.makedirs(folder3)
        print(f"创建目标文件夹: {folder3}")
    
    # 从市场中获取中心价时间序列并保存到文件中
    filename = os.path.join(folder1, f"mid_price_{save_num}.csv")
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Timestamp', 'Price'])
        # 遍历二维列表并写入数据
        for price in market.mid_price:
            writer.writerow([price[0], price[1]])

    # 从市场中获取订单簿时间序列
    filename = os.path.join(folder2, f"order_book_{save_num}.csv")
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Timestamp', 'OrderBook'])
        # 遍历二维列表并写入数据
        for order in market.orders:
            writer.writerow([order[0], order[1]])

    # 从市场中获取逐笔成交数据时间序列
    filename = os.path.join(folder3, f"match_result_{save_num}.csv")
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Timestamp', 'MatchResult'])
        # 遍历二维列表并写入数据
        for match in market.match_result:
            writer.writerow([match[0], match[1]])


# 模拟中的交易者类型
trader_type = ["Fundamental_Trader", "Long_term_Momentum_Trader", "Short_term_Momentum_Trader", "Noise_Trader"]

# 加载模型参数
param_file_path = 'model/model_params.tsf'
params = load_params(param_file_path)

# 读取输入数据并预处理
# data_file_path = 'new_data_experiment/SHL2_TAQ_600519_202401-202402_defreq.csv'
# prices, dates, fundamental_value = load_data(data_file_path)

# 不需要真实数据。时间戳、基本价值量和开盘价已经在参数文件中
dates = params['timestamps']
fundamental_value = params['fundamental_value']
open_price = params['open_price']

# -------运行ABM模型----------
# 设置生成数据的时间序列条数(每条数据包含和真实数据长度相同的价格序列、订单簿序列和成交序列，分别保存在三个文件夹中，相同编号的为同一组生成数据)
num_epoch = 10

# 设置生成时间序列的时间点样本数（暂无基本价值量推出机制，时间点样本数需小于真实数据最大长度8880）
# 序列的时间片开头与真实数据起始时间对齐
num_samples = 1000

# 判断要生成的时间点样本是否超出了范围
if num_samples > len(dates):
    print(f'生成长度超过当前样例时间片范围，当前时间序列生成长度为{len(dates)}。')
else:
    print(f'当前时间序列生成长度为{num_samples}。')

# 循环生成指定条数的时间序列数据，并保存到指定文件夹
for simulate_step in range(num_epoch):
    # 创建实例
    traders, exchange, market = create_instance(params, fundamental_value, open_price)
    # 市场模拟
    _, _, market = simulate_market(traders, exchange, market, open_price, dates, trader_type, params, num_samples)
    # 保存模拟结果
    save_samples(market, simulate_step, "synthetic_data")
    # 打印进度
    if simulate_step % 10 == 0:
        print("已生成时间序列数：", simulate_step)


# 保存合成数据（文件夹下会生成mid_price.csv、order_book.csv、match_result.csv三个文件）
# save_synthetic_data(market, "synthetic_data")     # 存放合成数据的文件夹路径
