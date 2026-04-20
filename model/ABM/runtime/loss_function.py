import numpy as np
import pandas as pd
import statsmodels.api as sm
import ot
import math
from scipy.stats import entropy, wasserstein_distance


def non_overlapping_block_bootstrap(data, block_size, n_samples):
    """
    非重叠块自助法
    :param data: 输入时间序列数据
    :param block_size: 块的大小
    :param n_samples: 需要生成的样本数量
    :return: 生成的重采样样本
    """
    n = len(data)
    # 计算可以形成的块的数量
    num_blocks = n // block_size
    # 创建块, 末尾数据会被丢弃
    blocks = [data[i * block_size:(i + 1) * block_size] for i in range(num_blocks)]
    blocks = np.array(blocks)
    
    # 进行重采样
    sampled_data = []
    for _ in range(n_samples):
        sampled_blocks = blocks[np.random.choice(num_blocks, size=num_blocks, replace=False)]
        # 将块拼接成一个样本
        sampled_data.append(np.concatenate(sampled_blocks))
    
    return np.array(sampled_data)


def block_bootstrap(true_prices, block_size, sample_nums):

    # 收集采样序列的四个指标
    hills = []
    vols = []
    acfs = []
    square_acfs = []

    # 收益自相关和平方收益自相关使用的滞后值
    lags = [30, 31, 32, 60, 61, 62, 90, 91, 92]
    square_lags = [1, 2, 3, 30, 31, 32, 60, 61, 62, 90, 91, 92]

    # 对价格序列重采样
    true_samples = non_overlapping_block_bootstrap(true_prices, block_size, sample_nums)

    # 计算样本统计值(hill、vol、acf、square_acf)
    for sample in true_samples:
        # 将价格序列处理成收益率序列
        returns = price_to_return(sample)

        # 使用希尔估计计算尾部指数（取序列的5%作为k值）
        abs_returns = np.abs(returns)
        k = int(len(returns) * 0.05)
        hill = hill_estimator(abs_returns, k)
        hills.append(hill)

        # 计算年化波动率
        annual_vol = calculate_annual_vol(returns)
        vols.append(annual_vol)

        # 计算收益自相关
        acf = calculate_acf(returns, lags)
        acf_mean = sum(acf) / len(acf)
        acfs.append(acf_mean)

        # 计算平方收益自相关
        square_returns = [r ** 2 for r in returns]
        square_acf = calculate_acf(square_returns, square_lags)
        square_acf_mean = sum(square_acf) / len(square_acf)
        square_acfs.append(square_acf_mean)


    # 计算抽样方差（无偏估计）
    var_hill = np.var(np.array(hills), ddof=1)
    var_vol = np.var(np.array(vols), ddof=1)
    var_acf = np.var(np.array(acfs), ddof=1)
    var_square_acf = np.var(np.array(square_acfs), ddof=1)

    # 计算四个指标的系数
    cof_hill = (1 / var_hill) * 1e-6
    cof_vol = (1 / var_vol) * 1e-6
    cof_acf = (1 / var_acf) * 1e-6
    cof_square_acf = (1 / var_square_acf) * 1e-6
    # cof_hill = 1 / var_hill
    # cof_vol = 1 / var_vol
    # cof_acf = 1 / var_acf
    # cof_square_acf = 1 / var_square_acf

    # 封装成字典
    cof_dict = {
        'hill': cof_hill,
        'vol': cof_vol,
        'acf': cof_acf,
        'sacf': cof_square_acf
    }

    return cof_dict

# 将价格序列处理成日收益率序列（1分钟）
def price_to_daily_return(prices):
    daily_returns = []
    for i in range(0, len(prices) - 239, 240):
        daily_return = (prices[i + 239] - prices[i]) / prices[i]
        daily_returns.append(daily_return)
    return daily_returns


# 将价格序列处理成收益率序列的函数
def price_to_return(prices):
    prices = pd.Series(prices)
    if (prices <= 0).any():
        raise ValueError("价格序列中包含小于或等于 0 的值，请先清理数据。")
    else:
        returns = prices.pct_change().dropna()
        returns = returns.tolist()
        return returns

# 希尔估计器
def hill_estimator(data, k):
    sorted_data = np.sort(data)[::-1]                               # 将数据按照从大到小排序
    top_k_values = sorted_data[:k]                                  # 选择最大的k个值
    log_top_k_values = np.log(top_k_values)                         # 对这k个值取对数
    log_ranks = np.log(np.arange(1, k + 1))                         # 计算样本对应秩的对数
    slope, intercept = np.polyfit(log_ranks, log_top_k_values, 1)   # 使用线性拟合来计算斜率
    tail_index = -slope                                             # 斜率的负值即为尾部指数的估计值
    
    return tail_index

'''算年化波动率的函数(通过分钟收益率标准差计算)
def calculate_annual_vol(returns):
    # 一年有 252 个交易日，每天 240 分钟(4个小时)
    T = 252 * 240
    annual_vol = np.std(returns) * np.sqrt(T)
    return annual_vol'''

# 计算年化波动率的函数(通过日收益率计算）
def calculate_annual_vol(returns):
    # 一年有 252 个交易日
    T = 252
    annual_vol = np.std(returns) * np.sqrt(T)
    return annual_vol

# 计算自相关的函数
def calculate_acf(returns, lags):
    all_acf = sm.tsa.acf(returns, nlags=max(lags))
    acf = [all_acf[i] for i in lags]
    return acf

# 计算多档行情数据的 Wasserstein 距离（只计算列方向的均值）
def calculate_Wasserstein(true_market, simulate_market):
    """
    :param true_market: 真实多档位市场行情 (buy1,sell1,bc1,sc1...)
    :param simulate_market: 模拟多档位市场行情 (buy1,sell1,bc1,sc1...)
    :return: 列方向的 Wasserstein 距离均值
    """
    # 将二维时间序列转换为numpy数组
    true_market_array = np.array(true_market)
    simulate_market_array = np.array(simulate_market)

    # 初始化一个空列表存储每一列的距离
    wasserstein_distances = []

    # 遍历每一列，计算距离
    for col in range(true_market_array.shape[1]):
        dist = wasserstein_distance(true_market_array[:, col], simulate_market_array[:, col])
        wasserstein_distances.append(dist)

    # 计算平均值
    average_wasserstein = np.mean(wasserstein_distances)
    # print("average_column_distance: ", average_wasserstein)

    return average_wasserstein



# 损失函数
def loss_function(cof_dict, true_prices, simulate_prices, true_markets, simulated_markets):
    """
    :param cof_dict: 损失函数权重字典(hill, vol, acf, sacf)
    :param true_prices: 真实一分钟频率行情价格
    :param simulate_prices: 模拟一分钟频率行情价格
    :param true_market: 真实多档位市场行情 (buy1,sell1,bc1,sc1...)
    :param simulate_market: 模拟多档位市场行情 (buy1,sell1,bc1,sc1...)
    :return: 列方向的 Wasserstein 距离均值
    """
    # 将真实价格序列和虚拟价格序列处理成收益率序列
    true_returns = price_to_return(true_prices)
    simulate_returns = price_to_return(simulate_prices)

    # 使用希尔估计计算尾部指数（取序列的5%作为k值）
    # 计算绝对收益序列
    abs_t_returns = np.abs(true_returns)
    abs_s_returns = np.abs(simulate_returns)

    k = int(len(true_returns) * 0.05)

    true_hill = hill_estimator(abs_t_returns, k)
    simulate_hill = hill_estimator(abs_s_returns, k)

    delta_hill = abs(simulate_hill - true_hill)

    # 计算年化波动率
    t_annual_vol = calculate_annual_vol(true_returns)
    s_annual_vol = calculate_annual_vol(simulate_returns)

    delta_vol = abs(s_annual_vol - t_annual_vol)

    # 计算收益自相关
    lags = [30, 31, 32, 60, 61, 62, 90, 91, 92]

    t_acf = calculate_acf(true_returns, lags)
    s_acf = calculate_acf(simulate_returns, lags)
    
    delta_acf = [abs(s - t) for s, t in zip(s_acf, t_acf)]

    delta_acf_mean = sum(delta_acf) / len(delta_acf)

    # 计算平方收益自相关
    square_t_returns = [r ** 2 for r in true_returns]
    square_s_returns = [r ** 2 for r in simulate_returns]

    square_lags = [1, 2, 3, 30, 31, 32, 60, 61, 62, 90, 91, 92]

    t_square_acf = calculate_acf(square_t_returns, square_lags)
    s_square_acf = calculate_acf(square_s_returns, square_lags)

    delta_square_acf = [abs(s - t) for s, t in zip(s_square_acf, t_square_acf)]

    delta_square_acf_mean = sum(delta_square_acf) / len(delta_square_acf)

    # --- 补充：多档行情的Wasserstein距离 ---------
    # wasserstein_distance_col = calculate_Wasserstein(true_markets, simulated_markets)
    
    # loss = cof_hill * delta_hill + cof_vol * delta_vol + cof_acf * delta_acf_mean + cof_square_acf * delta_square_acf_mean + wasserstein_distance_row + wasserstein_distance_col
    loss = cof_dict['hill'] * delta_hill + cof_dict['vol'] * delta_vol + cof_dict['acf'] * delta_acf_mean + cof_dict['sacf'] * delta_square_acf_mean

    return loss



