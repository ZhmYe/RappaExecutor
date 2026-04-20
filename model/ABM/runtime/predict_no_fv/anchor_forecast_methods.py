# -*- coding: utf-8 -*-
"""
可插拔的基本面锚点预测方法（仅使用历史数据，不含未来信息）。
"""

from __future__ import annotations

import numpy as np


def _to_arr(history_prices):
    arr = np.asarray(history_prices, dtype=float).ravel()
    if arr.size == 0:
        raise ValueError("history_prices 不能为空")
    return arr


def forecast_kalman_rw(history_prices, horizon=1, transition_cov=0.0001, observation_cov=2.0):
    """
    方案1：Kalman + Random Walk
    这里用纯 numpy 的局部水平模型滤波，未来期望值=当前滤波状态。
    """
    y = _to_arr(history_prices)
    q, r = float(transition_cov), float(observation_cov)
    x, p = float(y[0]), float(r)
    for k in range(1, len(y)):
        # predict
        x_pred = x
        p_pred = p + q
        # update
        k_gain = p_pred / (p_pred + r)
        x = x_pred + k_gain * (float(y[k]) - x_pred)
        p = (1.0 - k_gain) * p_pred
    return np.full(int(horizon), x, dtype=float)


def forecast_holt(history_prices, horizon=1, alpha=0.4, beta=0.2):
    """
    方案2：Holt 线性趋势（加法）。
    """
    y = _to_arr(history_prices)
    alpha = float(alpha)
    beta = float(beta)
    if len(y) == 1:
        return np.full(int(horizon), float(y[0]), dtype=float)

    level = float(y[0])
    trend = float(y[1] - y[0])
    for t in range(1, len(y)):
        prev_level = level
        level = alpha * float(y[t]) + (1.0 - alpha) * (level + trend)
        trend = beta * (level - prev_level) + (1.0 - beta) * trend

    hs = np.arange(1, int(horizon) + 1, dtype=float)
    return level + hs * trend


def forecast_mean_reversion(history_prices, horizon=1, window_size=30, reversion_speed=0.05):
    """
    方案4：滑动窗口均值回归外推。
    """
    y = _to_arr(history_prices)
    w = int(max(2, min(window_size, len(y))))
    lam = float(reversion_speed)
    eq = float(np.mean(y[-w:]))
    dev = float(y[-1] - eq)

    hs = np.arange(1, int(horizon) + 1, dtype=float)
    return eq + dev * ((1.0 - lam) ** hs)


def forecast_anchor(method_name, history_prices, horizon=1, params=None):
    """
    统一接口：
    method_name: kalman_rw | holt | mean_reversion
    """
    params = params or {}
    name = method_name.lower().strip()
    if name == "kalman_rw":
        return forecast_kalman_rw(history_prices, horizon=horizon, **params)
    if name == "holt":
        return forecast_holt(history_prices, horizon=horizon, **params)
    if name == "mean_reversion":
        return forecast_mean_reversion(history_prices, horizon=horizon, **params)
    raise ValueError(f"未知 method_name: {method_name}")

