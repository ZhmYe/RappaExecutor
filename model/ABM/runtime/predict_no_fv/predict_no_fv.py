#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
predict_no_fv.py

目标：
- 仅需一个 CSV 输入即可预测未来价格
- 默认自动识别时间列/价格列
- 默认自动调参并可自动选择最优方案
- 输出精简 CSV：Forecast_Time, Predicted_Price

用法示例：
python predict_no_fv.py --input_csv 600000.csv
python predict_no_fv.py --input_csv xxx.csv --method holt --horizon 30
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay
from scipy.stats import norm

from anchor_forecast_methods import forecast_anchor
from order import Order
from exchange import Exchange
from market import Market
from trader import Fundamental_Trader, Momentum_Trader, Noise_Trader
import config_600000 as base_config


TIME_CANDIDATES = ["Time", "Date", "Datetime", "timestamp", "time", "date"]
PRICE_CANDIDATES = ["close", "Close", "price", "Price", "last", "Last"]
FV_CANDIDATES = ["fv", "FV", "fundamental_value", "FundamentalValue", "fundamental", "Fundamental"]


METHOD_PARAM_GRID: Dict[str, List[Dict[str, float]]] = {
    "kalman_rw": [
        {"transition_cov": 1e-5, "observation_cov": 1.0},
        {"transition_cov": 1e-4, "observation_cov": 2.0},
        {"transition_cov": 5e-4, "observation_cov": 4.0},
    ],
    "holt": [
        {"alpha": 0.2, "beta": 0.05},
        {"alpha": 0.4, "beta": 0.1},
        {"alpha": 0.6, "beta": 0.2},
    ],
    "mean_reversion": [
        {"window_size": 10, "reversion_speed": 0.02},
        {"window_size": 20, "reversion_speed": 0.05},
        {"window_size": 30, "reversion_speed": 0.1},
        {"window_size": 60, "reversion_speed": 0.2},
    ],
}

ABM_VOL_LOOKBACK = 2400
ABM_BETA_BASE = 10.0
ABM_BETA_MID = 25.0
ABM_BETA_HIGH = 40.0
ABM_VOL_MID = 0.008
ABM_VOL_HIGH = 0.015
ABM_VOL_MULT = 1.3
ABM_PRICE_FLOOR = 0.01
ABM_PRICE_CEIL = 10000.0
ABM_ANCHOR_MIX = 0.8
ABM_OPEN_MIX = 0.9
CRASH_THRESHOLD = 0.05  # 5% drop threshold for crash probability
DISPLAY_PROB_FLOOR = 0.01
DISPLAY_PROB_CEIL = 0.99
MIN_SIGMA_RATIO = 0.005


@dataclass
class BestConfig:
    method: str
    params: Dict[str, float]
    cv_mae: float


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="No-FV future price prediction")
    p.add_argument(
        "--input_mode",
        default="default",
        choices=["default", "manual", "auto"],
        help="default=优先600000.csv, manual=使用--input_csv, auto=自动扫描当前目录可用CSV",
    )
    p.add_argument("--input_csv", default="", help="Input CSV path (manual模式下建议提供)")
    p.add_argument("--method", default="kalman_rw", choices=["auto", "kalman_rw", "holt", "mean_reversion", "abm_fv"])
    p.add_argument("--horizon", type=int, default=1, help="Forecast steps (default: 1 business day)")
    p.add_argument("--tune", default="auto", choices=["auto", "off"], help="Auto tune params or not")
    p.add_argument("--output_csv", default="", help="Reserved; output is fixed to predict_fv.csv")
    p.add_argument("--meta_json", default="", help="Optional meta info output path")
    p.add_argument("--fv_next", type=float, default=np.nan, help="方案abm_fv首日FV输入值")
    p.add_argument("--fv_file", default="", help="abm_fv分钟级FV输入文件（未来1天1min）")
    p.add_argument("--model_params_json", default="", help="abm_fv使用的离线参数文件 model_params.json（可选）")
    p.add_argument("--lookback_days", type=int, default=7, help="abm_fv历史回看交易日天数（默认7）")
    p.add_argument("--intraday_steps", type=int, default=240, help="abm_fv单日分钟步数（默认240）")
    p.add_argument("--abm_rounds", type=int, default=5, help="方案abm_fv每日ABM仿真轮数")
    p.add_argument(
        "--risk_drop_levels",
        default="0.05",
        help="逗号分隔的下跌概率阈值；默认 0.05，表示5%闪崩标准",
    )
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def is_interactive_launch() -> bool:
    # 仅在“无参数直接运行”时进入交互模式
    return len(sys.argv) == 1


def list_csv_files() -> List[str]:
    files = [fn for fn in os.listdir(".") if fn.lower().endswith(".csv")]
    files.sort()
    return files


def ask_choice(prompt: str, options: List[str], default_idx: int = 0) -> str:
    while True:
        print(prompt)
        for i, op in enumerate(options, 1):
            tag = " (default)" if i - 1 == default_idx else ""
            print(f"  {i}. {op}{tag}")
        raw = input("请输入序号并回车: ").strip()
        if not raw:
            return options[default_idx]
        if raw.isdigit():
            k = int(raw)
            if 1 <= k <= len(options):
                return options[k - 1]
        print("输入无效，请重试。")


def ask_csv_filename(default_csv: str) -> str:
    while True:
        raw = input(f"请输入CSV文件名（回车默认 {default_csv}）: ").strip()
        chosen = raw if raw else default_csv
        if os.path.exists(chosen) and chosen.lower().endswith(".csv"):
            return chosen
        print(f"文件不存在或不是CSV: {chosen}，请重试。")


def ask_fv_filename() -> str:
    while True:
        raw = input("请输入FV文件名（未来1天1min）: ").strip()
        if raw and os.path.exists(raw) and raw.lower().endswith(".csv"):
            return raw
        print(f"FV文件不存在或不是CSV: {raw}，请重试。")


def interactive_collect(args: argparse.Namespace) -> argparse.Namespace:
    csv_files = list_csv_files()
    if not csv_files:
        raise ValueError("当前目录没有CSV文件，无法交互选择输入文件")

    default_csv = "600000.csv" if "600000.csv" in csv_files else csv_files[0]
    chosen_csv = ask_csv_filename(default_csv)

    method_options = ["auto", "kalman_rw", "holt", "mean_reversion", "abm_fv"]
    chosen_method = ask_choice("请选择预测方案：", method_options, default_idx=0)

    args.input_mode = "manual"
    args.input_csv = chosen_csv
    args.method = chosen_method
    if chosen_method == "abm_fv":
        args.fv_file = ask_fv_filename()
        args.lookback_days = 7
        args.intraday_steps = 240
    return args


def detect_time_col(df: pd.DataFrame) -> str:
    for c in TIME_CANDIDATES:
        if c in df.columns:
            return c
    best_col, best_ok = None, -1
    for c in df.columns:
        parsed = pd.to_datetime(df[c], errors="coerce")
        ok = int(parsed.notna().sum())
        if ok > best_ok:
            best_col, best_ok = c, ok
    if best_col is None or best_ok <= 0:
        raise ValueError("无法识别时间列，请确保 CSV 包含可解析的时间字段")
    return best_col


def detect_price_col(df: pd.DataFrame, time_col: str) -> str:
    for c in PRICE_CANDIDATES:
        if c in df.columns:
            return c
    best_col, best_ok = None, -1
    for c in df.columns:
        if c == time_col:
            continue
        series = pd.to_numeric(df[c], errors="coerce")
        ok = int(series.notna().sum())
        if ok > best_ok:
            best_col, best_ok = c, ok
    if best_col is None or best_ok <= 0:
        raise ValueError("无法识别价格列，请确保 CSV 至少有一列数值价格")
    return best_col


def load_series(csv_path: str) -> Tuple[pd.Series, pd.Series, str, str]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"文件不存在: {csv_path}")

    df = pd.read_csv(csv_path)
    if df.empty:
        raise ValueError("输入 CSV 为空")

    time_col = detect_time_col(df)
    price_col = detect_price_col(df, time_col)

    ts = pd.to_datetime(df[time_col], errors="coerce")
    px = pd.to_numeric(df[price_col], errors="coerce")
    ok = ts.notna() & px.notna()
    ts = ts[ok]
    px = px[ok]

    if len(px) < 30:
        raise ValueError("有效数据太少（<30），无法稳定预测")

    temp = pd.DataFrame({"ts": ts.values, "px": px.values}).sort_values("ts")

    # 自动按“每日最后价格”聚合，提升泛化稳定性
    temp["date_only"] = temp["ts"].dt.floor("D")
    daily = temp.groupby("date_only", as_index=False)["px"].last()
    series_t = pd.to_datetime(daily["date_only"])
    series_p = pd.to_numeric(daily["px"], errors="coerce")

    if len(series_p) < 20:
        # 若日聚合后太短，则退回原始序列
        series_t = temp["ts"].reset_index(drop=True)
        series_p = temp["px"].reset_index(drop=True)

    return series_t.reset_index(drop=True), series_p.reset_index(drop=True), time_col, price_col


def load_intraday_series(csv_path: str) -> Tuple[pd.Series, pd.Series, str, str]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"文件不存在: {csv_path}")
    df = pd.read_csv(csv_path)
    if df.empty:
        raise ValueError("输入 CSV 为空")
    time_col = detect_time_col(df)
    price_col = detect_price_col(df, time_col)
    ts = pd.to_datetime(df[time_col], errors="coerce")
    px = pd.to_numeric(df[price_col], errors="coerce")
    ok = ts.notna() & px.notna()
    ts = ts[ok]
    px = px[ok]
    if len(px) < 30:
        raise ValueError("有效数据太少（<30），无法稳定预测")
    temp = pd.DataFrame({"ts": ts.values, "px": px.values}).sort_values("ts")
    return temp["ts"].reset_index(drop=True), temp["px"].reset_index(drop=True), time_col, price_col


def detect_fv_col(df: pd.DataFrame, time_col: str) -> str:
    for c in FV_CANDIDATES:
        if c in df.columns:
            return c
    return detect_price_col(df, time_col)


def load_fv_intraday_series(fv_file: str) -> Tuple[pd.Series, pd.Series, str, str]:
    if not fv_file:
        raise ValueError("abm_fv模式需要提供 --fv_file")
    if not os.path.exists(fv_file):
        raise FileNotFoundError(f"FV文件不存在: {fv_file}")
    df = pd.read_csv(fv_file)
    if df.empty:
        raise ValueError("FV文件为空")
    time_col = detect_time_col(df)
    fv_col = detect_fv_col(df, time_col)
    ts = pd.to_datetime(df[time_col], errors="coerce")
    fv = pd.to_numeric(df[fv_col], errors="coerce")
    ok = ts.notna() & fv.notna()
    ts = ts[ok]
    fv = fv[ok]
    if len(fv) < 20:
        raise ValueError("FV文件有效数据太少（<20）")
    temp = pd.DataFrame({"ts": ts.values, "fv": fv.values}).sort_values("ts")
    return temp["ts"].reset_index(drop=True), temp["fv"].reset_index(drop=True), time_col, fv_col


def parse_risk_drop_levels(raw: str) -> Tuple[float, ...]:
    levels = []
    for item in str(raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        value = float(item)
        if value <= 0 or value >= 1:
            raise ValueError(f"risk drop level must be between 0 and 1: {value}")
        levels.append(value)
    if not levels:
        return (0.05,)
    return tuple(dict.fromkeys(levels))


def load_model_params_json(path: str) -> dict:
    if not path:
        return {}
    if not os.path.exists(path):
        raise FileNotFoundError(f"model_params.json 不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("model_params.json 根对象必须是 JSON object")
    return data


def build_abm_cfg_from_model_params(payload: dict, code_fallback: str = "") -> dict:
    """
    Build ABM config dict for intraday abm_fv simulation.
    Uses offline params when provided, otherwise falls back to base_config.
    """
    structural = payload.get("structural_params", {}) if isinstance(payload.get("structural_params", {}), dict) else {}
    calibrated = payload.get("calibrated_params", {}) if isinstance(payload.get("calibrated_params", {}), dict) else {}

    def pick(name: str, default: float):
        if name in calibrated:
            try:
                return float(calibrated[name])
            except Exception:
                return default
        if name in structural:
            try:
                return float(structural[name])
            except Exception:
                return default
        return default

    def pick_int(name: str, default: int):
        if name in structural:
            try:
                return int(structural[name])
            except Exception:
                return default
        return default

    code = str(payload.get("code", "")).strip() or code_fallback or base_config.STOCK_SYMBOL
    if code.isdigit() and len(code) == 6:
        stock_symbol = code
    else:
        stock_symbol = base_config.STOCK_SYMBOL

    cfg = {
        "STOCK_SYMBOL": stock_symbol,
        "N_FT": pick_int("N_FT", int(getattr(base_config, "N_FT", 30))),
        "S_FT": pick_int("S_FT", int(getattr(base_config, "S_FT", 1))),
        "N_LMT": pick_int("N_LMT", int(getattr(base_config, "N_LMT", 30))),
        "N_NT": pick_int("N_NT", int(getattr(base_config, "N_NT", 30))),
        "ALPHA_L": pick("ALPHA_L", float(getattr(base_config, "ALPHA_L", 0.001))),
        "GAMMA": float(getattr(base_config, "GAMMA", 10.0)),
        "SIGMA_L": float(getattr(base_config, "SIGMA_L", 0.3)),
        # calibrated params used by traders
        "MU_L": pick("MU_L", float(getattr(base_config, "MU_L", -1.6))),
        "K1": pick("K1", float(getattr(base_config, "K1", 1.0))),
        "K2": pick("K2", float(getattr(base_config, "K2", 1.0))),
        "DELTA_NT": pick("DELTA_NT", float(getattr(base_config, "DELTA_NT", 1.0))),
    }
    return cfg


def select_last_n_days_intraday(
    times: pd.Series, prices: pd.Series, lookback_days: int
) -> Tuple[pd.Series, pd.Series]:
    df = pd.DataFrame({"ts": pd.to_datetime(times), "px": pd.to_numeric(prices, errors="coerce")}).dropna()
    if df.empty:
        raise ValueError("历史价格序列为空")
    df["date_only"] = df["ts"].dt.floor("D")
    unique_dates = sorted(df["date_only"].unique())
    if len(unique_dates) > int(lookback_days):
        keep = set(unique_dates[-int(lookback_days):])
        df = df[df["date_only"].isin(keep)]
    return df["ts"].reset_index(drop=True), df["px"].reset_index(drop=True)


def can_use_csv_quick(csv_path: str) -> bool:
    try:
        df = pd.read_csv(csv_path, nrows=300)
        if df.empty:
            return False
        tcol = detect_time_col(df)
        pcol = detect_price_col(df, tcol)
        ts = pd.to_datetime(df[tcol], errors="coerce")
        px = pd.to_numeric(df[pcol], errors="coerce")
        valid = (ts.notna() & px.notna()).sum()
        return int(valid) >= 10
    except Exception:
        return False


def auto_pick_csv_from_cwd() -> str:
    candidates = []
    for fn in os.listdir("."):
        if not fn.lower().endswith(".csv"):
            continue
        # 过滤明显的预测输出文件，优先原始行情数据
        lower = fn.lower()
        if "forecast" in lower or "prediction" in lower or "scheme" in lower:
            continue
        candidates.append(fn)

    # 若过滤后为空，则退回所有CSV
    if not candidates:
        candidates = [fn for fn in os.listdir(".") if fn.lower().endswith(".csv")]

    # 先按修改时间降序，之后用有效样本数再筛选
    candidates.sort(key=lambda x: os.path.getmtime(x), reverse=True)

    best_file = None
    best_len = -1
    for c in candidates:
        if not can_use_csv_quick(c):
            continue
        try:
            _, p, _, _ = load_series(c)
            n = int(len(p))
            if n > best_len:
                best_len = n
                best_file = c
        except Exception:
            continue

    if best_file is not None and best_len >= 30:
        return best_file
    raise ValueError("auto模式未找到可用CSV（需要可解析时间列与价格列）")


def resolve_input_csv(args: argparse.Namespace) -> str:
    mode = args.input_mode
    manual_path = args.input_csv.strip()

    if mode == "manual":
        if not manual_path:
            raise ValueError("manual模式需要提供 --input_csv")
        return manual_path

    if mode == "default":
        if manual_path:
            return manual_path
        if os.path.exists("600000.csv"):
            return "600000.csv"
        # default找不到600000时自动兜底扫描
        return auto_pick_csv_from_cwd()

    # mode == auto
    if manual_path and os.path.exists(manual_path):
        return manual_path
    return auto_pick_csv_from_cwd()


def build_future_time_index(last_time: pd.Timestamp, horizon: int) -> List[pd.Timestamp]:
    # 仅生成工作日（Business Day）
    start = pd.Timestamp(last_time) + BDay(1)
    idx = pd.bdate_range(start=start, periods=horizon, freq="B")
    return list(idx.to_pydatetime())


def estimate_steps_per_day(csv_path: str, time_col: str) -> int:
    """估计ABM每日步数。优先用原始CSV逐日条数中位数；不足时回退240。"""
    try:
        df = pd.read_csv(csv_path, usecols=[time_col])
        ts = pd.to_datetime(df[time_col], errors="coerce")
        ts = ts[ts.notna()]
        if len(ts) == 0:
            return 240
        counts = ts.dt.floor("D").value_counts()
        if len(counts) == 0:
            return 240
        steps = int(np.median(counts.values))
        return max(20, min(480, steps))
    except Exception:
        return 240


def run_scheme5_abm_fv(prices: np.ndarray, fv_next: float, horizon: int, steps_per_day: int, abm_rounds: int) -> np.ndarray:
    """
    方案5：
    Day1 anchor=用户输入FV；
    Day2..N anchor=平滑更新(保留外生FV影响，避免快速崩塌)；
    每日 open=平滑递推（Day1用最近真实收盘）；
    ABM多轮均值作为当日预测收盘。
    """
    if np.isnan(fv_next):
        raise ValueError("方案abm_fv需要提供 --fv_next")
    history = [float(x) for x in prices.tolist()]
    open_used = float(np.clip(history[-1], ABM_PRICE_FLOOR, ABM_PRICE_CEIL))
    anchor = float(np.clip(fv_next, ABM_PRICE_FLOOR, ABM_PRICE_CEIL))
    preds: List[float] = []
    rounds = max(1, int(abm_rounds))
    steps = max(20, int(steps_per_day))

    for _ in range(int(horizon)):
        vol, beta = abm_get_vol_beta(history, len(history))
        vol_sim = vol * ABM_VOL_MULT
        closes = []
        for _r in range(rounds):
            try:
                path = abm_run_single_simulation(open_used, anchor, beta, vol_sim, steps)
                close_v = float(path[-1])
            except (OverflowError, ZeroDivisionError, ValueError, FloatingPointError):
                close_v = float(open_used)
            if not np.isfinite(close_v):
                close_v = float(open_used)
            close_v = float(np.clip(close_v, ABM_PRICE_FLOOR, ABM_PRICE_CEIL))
            closes.append(close_v)
        pred_close = float(np.mean(closes)) if closes else float(open_used)
        if not np.isfinite(pred_close):
            pred_close = float(open_used)
        pred_close = float(np.clip(pred_close, ABM_PRICE_FLOOR, ABM_PRICE_CEIL))
        preds.append(pred_close)
        history.append(pred_close)
        # 平滑递推：减轻“无论输入什么都单边下跌”的强自反馈
        open_used = float(np.clip(ABM_OPEN_MIX * pred_close + (1.0 - ABM_OPEN_MIX) * anchor,
                                  ABM_PRICE_FLOOR, ABM_PRICE_CEIL))
        anchor = float(np.clip(ABM_ANCHOR_MIX * anchor + (1.0 - ABM_ANCHOR_MIX) * pred_close,
                               ABM_PRICE_FLOOR, ABM_PRICE_CEIL))

    return np.asarray(preds, dtype=float)


def abm_get_vol_beta(prices: List[float], end_idx: int) -> Tuple[float, float]:
    if end_idx < 2:
        return 0.01, ABM_BETA_BASE
    history = prices[:end_idx]
    recent = history[-ABM_VOL_LOOKBACK:]
    vol = float(np.std(np.diff(recent)))
    if np.isnan(vol) or vol <= 0:
        vol = 0.01
    beta = ABM_BETA_BASE
    if vol > ABM_VOL_HIGH:
        beta = ABM_BETA_HIGH
    elif vol > ABM_VOL_MID:
        beta = ABM_BETA_MID
    return vol, beta


def abm_run_single_simulation(start_price: float, anchor_price: float, beta: float, volatility: float, steps: int) -> List[float]:
    start_price = float(np.clip(start_price, ABM_PRICE_FLOOR, ABM_PRICE_CEIL))
    anchor_price = float(np.clip(anchor_price, ABM_PRICE_FLOOR, ABM_PRICE_CEIL))
    exchange = Exchange()
    market = Market()
    timestamp = 0

    exchange.add_order(Order(999, 0, base_config.STOCK_SYMBOL, start_price, 100, True, timestamp))
    exchange.add_order(Order(999, 0, base_config.STOCK_SYMBOL, start_price, 100, False, timestamp))

    traders = []
    tid = 0
    stock_symbol = base_config.STOCK_SYMBOL

    fv_vector = [anchor_price] * (steps + 200)
    for _ in range(base_config.N_FT):
        t = Fundamental_Trader(
            tid, 100000, {}, fv_vector, base_config.N_FT, base_config.S_FT, base_config.K1, base_config.K2
        )
        traders.append(t)
        tid += 1

    for _ in range(base_config.N_LMT):
        t = Momentum_Trader(
            tid, 100000, {}, base_config.N_LMT, base_config.ALPHA_L, beta, base_config.GAMMA, start_price
        )
        t.Rho = 0.3
        traders.append(t)
        tid += 1

    for _ in range(base_config.N_NT):
        t = Noise_Trader(tid, 100000, {}, base_config.N_NT, base_config.DELTA_NT)
        traders.append(t)
        tid += 1

    sim_prices = [start_price]
    current_mid = start_price
    market.update_simulation([], [], start_price, start_price, [], timestamp)

    for step in range(steps):
        timestamp = step + 1
        all_limit, all_market, all_cancel = [], [], []
        for t in traders:
            curr_price = market.price_trend[-1][1] if market.price_trend else start_price
            if isinstance(t, Fundamental_Trader):
                mm = t.trading_function(stock_symbol, timestamp, step, curr_price)
                all_market.extend(mm)
            elif isinstance(t, Momentum_Trader):
                dist = curr_price * (volatility * 2.5) * abs(np.random.randn())
                c, mm, l = t.trading_function(stock_symbol, timestamp, curr_price, dist)
                all_cancel.extend(c)
                all_market.extend(mm)
                all_limit.extend(l)
            elif isinstance(t, Noise_Trader):
                dist = curr_price * volatility * abs(np.random.randn())
                c, mm, l = t.trading_function(stock_symbol, timestamp, curr_price, dist)
                all_cancel.extend(c)
                all_market.extend(mm)
                all_limit.extend(l)

        for oid in all_cancel:
            exchange.del_order(oid)
        for lo in all_limit:
            exchange.add_order(lo)
        match_results = []
        for mo in all_market:
            match_results.extend(exchange.add_and_match_market_order(mo))

        mid = exchange.calculate_midprice()
        if mid:
            current_mid = mid
        if match_results:
            current_mid = match_results[-1][3]
        if not np.isfinite(current_mid):
            current_mid = start_price
        current_mid = float(np.clip(current_mid, ABM_PRICE_FLOOR, ABM_PRICE_CEIL))

        sim_prices.append(current_mid)
        market.update_simulation(exchange.orders, match_results, current_mid, current_mid, [], timestamp)

        if start_price > 0 and (current_mid - start_price) / start_price < -0.15:
            sim_prices.extend([current_mid] * (steps - step - 1))
            break

    return sim_prices


def abm_run_single_simulation_with_fv_path(
    start_price: float, fv_path: np.ndarray, beta: float, volatility: float, cfg: Optional[dict] = None
) -> np.ndarray:
    cfg = cfg or {}
    start_price = float(np.clip(start_price, ABM_PRICE_FLOOR, ABM_PRICE_CEIL))
    fv = np.asarray(fv_path, dtype=float)
    if len(fv) == 0:
        raise ValueError("fv_path is empty")
    fv = np.clip(fv, ABM_PRICE_FLOOR, ABM_PRICE_CEIL)

    exchange = Exchange()
    market = Market()
    timestamp = 0
    stock_symbol = str(cfg.get("STOCK_SYMBOL", base_config.STOCK_SYMBOL))
    exchange.add_order(Order(999, 0, stock_symbol, start_price, 100, True, timestamp))
    exchange.add_order(Order(999, 0, stock_symbol, start_price, 100, False, timestamp))

    traders = []
    tid = 0
    fv_vector = fv.tolist() + [float(fv[-1])] * 200
    n_ft = int(cfg.get("N_FT", base_config.N_FT))
    s_ft = int(cfg.get("S_FT", base_config.S_FT))
    k1 = float(cfg.get("K1", base_config.K1))
    k2 = float(cfg.get("K2", base_config.K2))
    n_lmt = int(cfg.get("N_LMT", base_config.N_LMT))
    alpha_l = float(cfg.get("ALPHA_L", base_config.ALPHA_L))
    gamma = float(cfg.get("GAMMA", base_config.GAMMA))
    delta_nt = float(cfg.get("DELTA_NT", base_config.DELTA_NT))
    n_nt = int(cfg.get("N_NT", base_config.N_NT))

    for _ in range(n_ft):
        t = Fundamental_Trader(
            tid, 100000, {}, fv_vector, n_ft, s_ft, k1, k2
        )
        traders.append(t)
        tid += 1
    for _ in range(n_lmt):
        t = Momentum_Trader(tid, 100000, {}, n_lmt, alpha_l, beta, gamma, start_price)
        t.Rho = 0.3
        traders.append(t)
        tid += 1
    for _ in range(n_nt):
        t = Noise_Trader(tid, 100000, {}, n_nt, delta_nt)
        traders.append(t)
        tid += 1

    sim_prices = [start_price]
    current_mid = start_price
    market.update_simulation([], [], start_price, start_price, [], timestamp)
    steps = int(len(fv))
    for step in range(steps):
        timestamp = step + 1
        all_limit, all_market, all_cancel = [], [], []
        for t in traders:
            curr_price = market.price_trend[-1][1] if market.price_trend else start_price
            if isinstance(t, Fundamental_Trader):
                mm = t.trading_function(stock_symbol, timestamp, step, curr_price)
                all_market.extend(mm)
            elif isinstance(t, Momentum_Trader):
                dist = curr_price * (volatility * 2.5) * abs(np.random.randn())
                c, mm, l = t.trading_function(stock_symbol, timestamp, curr_price, dist)
                all_cancel.extend(c)
                all_market.extend(mm)
                all_limit.extend(l)
            elif isinstance(t, Noise_Trader):
                dist = curr_price * volatility * abs(np.random.randn())
                c, mm, l = t.trading_function(stock_symbol, timestamp, curr_price, dist)
                all_cancel.extend(c)
                all_market.extend(mm)
                all_limit.extend(l)
        for oid in all_cancel:
            exchange.del_order(oid)
        for lo in all_limit:
            exchange.add_order(lo)
        match_results = []
        for mo in all_market:
            match_results.extend(exchange.add_and_match_market_order(mo))
        mid = exchange.calculate_midprice()
        if mid:
            current_mid = mid
        if match_results:
            current_mid = match_results[-1][3]
        if not np.isfinite(current_mid):
            current_mid = start_price
        current_mid = float(np.clip(current_mid, ABM_PRICE_FLOOR, ABM_PRICE_CEIL))
        sim_prices.append(current_mid)
        market.update_simulation(exchange.orders, match_results, current_mid, current_mid, [], timestamp)
    return np.asarray(sim_prices[1:], dtype=float)


def run_intraday_abm_fv(
    history_prices: np.ndarray,
    fv_intraday: np.ndarray,
    abm_rounds: int,
    cfg: Optional[dict] = None,
    crash_threshold: float = CRASH_THRESHOLD,
) -> Tuple[np.ndarray, np.ndarray, float]:
    history = [float(x) for x in history_prices.tolist()]
    if len(history) < 2:
        raise ValueError("历史价格长度不足")
    vol, beta = abm_get_vol_beta(history, len(history))
    vol_sim = vol * ABM_VOL_MULT
    start_price = float(np.clip(history[-1], ABM_PRICE_FLOOR, ABM_PRICE_CEIL))
    rounds = max(1, int(abm_rounds))
    all_paths = []
    for _ in range(rounds):
        try:
            path = abm_run_single_simulation_with_fv_path(start_price, fv_intraday, beta, vol_sim, cfg=cfg)
        except Exception:
            path = np.full(len(fv_intraday), start_price, dtype=float)
        if len(path) != len(fv_intraday):
            path = np.resize(path, len(fv_intraday))
        path = np.clip(path.astype(float), ABM_PRICE_FLOOR, ABM_PRICE_CEIL)
        all_paths.append(path)
    paths = np.vstack(all_paths)
    mean_path = np.mean(paths, axis=0)
    # empirical crash probability based on simulated paths
    threshold_price = start_price * (1.0 - float(crash_threshold))
    crashed = (np.min(paths, axis=1) <= threshold_price).astype(float)
    crash_prob_day = float(np.mean(crashed)) if len(crashed) else 0.0
    return mean_path, paths, crash_prob_day


def cv_mae_for_method(prices: np.ndarray, method: str, params: Dict[str, float]) -> float:
    n = len(prices)
    min_train = max(20, int(n * 0.5))
    folds = min(8, max(3, (n - min_train) // 5))
    if folds <= 0:
        return float("inf")

    errs = []
    # 步进 walk-forward：每个折只预测下一步
    step = max(1, (n - min_train - 1) // folds)
    for end in range(min_train, n - 1, step):
        hist = prices[:end]
        true_next = float(prices[end])
        pred_next = float(forecast_anchor(method, hist, horizon=1, params=params)[0])
        errs.append(abs(pred_next - true_next))

    if not errs:
        return float("inf")
    return float(np.mean(errs))


def auto_select_and_tune(prices: np.ndarray, method_opt: str, tune_opt: str) -> BestConfig:
    if method_opt != "auto":
        if tune_opt == "off":
            params = METHOD_PARAM_GRID[method_opt][0]
            return BestConfig(method=method_opt, params=params, cv_mae=float("nan"))
        best = None
        for p in METHOD_PARAM_GRID[method_opt]:
            score = cv_mae_for_method(prices, method_opt, p)
            if best is None or score < best.cv_mae:
                best = BestConfig(method=method_opt, params=p, cv_mae=score)
        return best

    # method = auto
    candidates = ["kalman_rw", "holt", "mean_reversion"]
    best_global = None
    for m in candidates:
        if tune_opt == "off":
            cand = BestConfig(method=m, params=METHOD_PARAM_GRID[m][0], cv_mae=cv_mae_for_method(prices, m, METHOD_PARAM_GRID[m][0]))
        else:
            cand = None
            for p in METHOD_PARAM_GRID[m]:
                score = cv_mae_for_method(prices, m, p)
                if cand is None or score < cand.cv_mae:
                    cand = BestConfig(method=m, params=p, cv_mae=score)
        if best_global is None or cand.cv_mae < best_global.cv_mae:
            best_global = cand
    return best_global


def main() -> None:
    args = parse_args()
    if is_interactive_launch():
        args = interactive_collect(args)
    np.random.seed(args.seed)

    input_csv = resolve_input_csv(args)
    risk_drop_levels = parse_risk_drop_levels(args.risk_drop_levels)

    if args.method == "abm_fv":
        hist_times, hist_prices, time_col, price_col = load_intraday_series(input_csv)
        hist_times, hist_prices = select_last_n_days_intraday(hist_times, hist_prices, args.lookback_days)
        fv_times, fv_values, _, _ = load_fv_intraday_series(args.fv_file)
        # intraday steps follow FV file length (C)
        steps = int(len(fv_values))
        y = hist_prices.astype(float).values
        payload = load_model_params_json(args.model_params_json) if args.model_params_json else {}
        cfg = build_abm_cfg_from_model_params(payload, code_fallback=os.path.splitext(os.path.basename(input_csv))[0])
        primary_crash_threshold = 0.05 if 0.05 in risk_drop_levels else risk_drop_levels[0]
        pred, paths, crash_prob_day = run_intraday_abm_fv(
            y,
            fv_values.astype(float).values,
            args.abm_rounds,
            cfg=cfg,
            crash_threshold=primary_crash_threshold,
        )
        future_times = pd.to_datetime(fv_times).tolist()
        best = BestConfig(
            method="abm_fv",
            params={"fv_file": args.fv_file, "model_params_json": args.model_params_json} if args.model_params_json else {"fv_file": args.fv_file},
            cv_mae=float("nan"),
        )
        sigma = np.nan
        last_close = float(y[-1]) if len(y) > 0 else np.nan
        out_df = pd.DataFrame({"Forecast_Time": future_times, "Predicted_Price": pred})
        source_freq = "intraday_1min"
        # Cumulative path probability: P(min price up to t <= start_price * (1 - X))
        start_price = float(y[-1]) if len(y) else float("nan")
        if np.isfinite(start_price):
            cummins = np.minimum.accumulate(paths, axis=1)
            for level in risk_drop_levels:
                pct = int(round(level * 100))
                threshold_price = start_price * (1.0 - level)
                crash_upto = (cummins <= threshold_price).mean(axis=0)
                out_df[f"Crash_Prob_{pct}pct"] = crash_upto
            primary_pct = int(round(primary_crash_threshold * 100))
            out_df["Crash_Prob"] = out_df[f"Crash_Prob_{primary_pct}pct"]
        else:
            for level in risk_drop_levels:
                pct = int(round(level * 100))
                out_df[f"Crash_Prob_{pct}pct"] = np.nan
            out_df["Crash_Prob"] = np.nan
    else:
        times, prices, time_col, price_col = load_series(input_csv)
        y = prices.astype(float).values
        best = auto_select_and_tune(y, args.method, args.tune)
        pred = forecast_anchor(best.method, y, horizon=args.horizon, params=best.params).astype(float)
        future_times = build_future_time_index(pd.Timestamp(times.iloc[-1]), args.horizon)
        out_df = pd.DataFrame({"Forecast_Time": future_times, "Predicted_Price": pred})
        sigma = np.nan
        last_close = float(y[-1]) if len(y) > 0 else np.nan
        if np.isfinite(best.cv_mae) and best.cv_mae > 0:
            sigma = float(best.cv_mae) * np.sqrt(np.pi / 2.0) * np.sqrt(max(1, args.horizon))
        else:
            if len(y) >= 2:
                naive_errors = np.abs(y[1:] - y[:-1]).astype(float)
                mae = float(np.nanmean(naive_errors))
                if np.isfinite(mae) and mae > 0:
                    sigma = mae * np.sqrt(np.pi / 2.0) * np.sqrt(max(1, args.horizon))
        if not np.isfinite(sigma) or sigma <= 0:
            sigma = abs(last_close) * MIN_SIGMA_RATIO if np.isfinite(last_close) and last_close != 0 else MIN_SIGMA_RATIO
        source_freq = "daily_or_fallback_raw"

    # Add probability columns for risk/threshold visualization.
    # Convention: use Prob_Drop_Xpct = P(Price <= last_close*(1-X)) under Normal(mean=pred, sd=sigma).
    drop_levels = risk_drop_levels

    for level in drop_levels:
        threshold = last_close * (1.0 - level)
        col = f"Prob_Drop_{int(level * 100)}pct"
        if not np.isfinite(sigma) or sigma <= 0:
            out_df[col] = np.nan
        else:
            z = (threshold - pred) / sigma  # vectorized for each horizon step
            out_df[col] = np.clip(norm.cdf(z), DISPLAY_PROB_FLOOR, DISPLAY_PROB_CEIL)

    # Daily methods: keep Crash_Prob aligned with configured standard, defaulting to 5%.
    if "Crash_Prob" not in out_df.columns:
        crash_level = 0.05 if 0.05 in drop_levels else drop_levels[0]
        out_df["Crash_Prob"] = out_df[f"Prob_Drop_{int(round(crash_level * 100))}pct"]

    # (B1) split outputs by frequency, keep predict_fv.csv as compatibility copy.
    compat_csv = args.output_csv or "predict_fv.csv"
    compat_dir = os.path.dirname(compat_csv)
    if compat_dir:
        os.makedirs(compat_dir, exist_ok=True)
    split_name = "predict_fv_intraday.csv" if source_freq == "intraday_1min" else "predict_fv_daily.csv"
    out_csv = os.path.join(compat_dir, split_name) if compat_dir else split_name
    out_df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    if os.path.abspath(compat_csv) != os.path.abspath(out_csv):
        out_df.to_csv(compat_csv, index=False, encoding="utf-8-sig")

    meta = {
        "input_csv": input_csv,
        "detected_time_col": time_col,
        "detected_price_col": price_col,
        "effective_points": int(len(y)),
        "source_frequency": source_freq,
        "method": best.method,
        "params": best.params,
        "cv_mae": best.cv_mae,
        "last_close": last_close,
        "assumed_sigma": float(sigma) if np.isfinite(sigma) else None,
        "drop_levels": list(drop_levels),
        "display_prob_floor": DISPLAY_PROB_FLOOR,
        "display_prob_ceil": DISPLAY_PROB_CEIL,
        "min_sigma_ratio": MIN_SIGMA_RATIO,
        "prob_definition": "Prob_Drop_Xpct = display-clipped P(Price <= last_close*(1-X)) under Normal(mean=pred, sd=assumed_sigma); ordinary models are clipped to [display_prob_floor, display_prob_ceil]; Crash_Prob_Xpct = simulated P(min price up to t <= last_close*(1-X)) in abm_fv mode",
        "horizon": args.horizon,
        "output_csv": out_csv,
    }
    if args.method == "abm_fv":
        meta["abm_rounds"] = int(args.abm_rounds)
        meta["lookback_days"] = int(args.lookback_days)
        meta["intraday_steps"] = int(steps)
        meta["fv_file"] = args.fv_file
        meta["model_params_json"] = args.model_params_json or None
        meta["horizon"] = 1
        meta["output_points"] = int(len(pred))
        meta["crash_threshold"] = float(primary_crash_threshold)
        meta["crash_prob_day"] = float(crash_prob_day)
        meta["crash_prob_day_by_level"] = {
            f"{int(round(level * 100))}pct": float(
                np.mean(np.min(paths, axis=1) <= start_price * (1.0 - level))
            ) if np.isfinite(start_price) else None
            for level in risk_drop_levels
        }
    meta_path = args.meta_json or "predict_fv_meta.json"
    meta_dir = os.path.dirname(meta_path)
    if meta_dir:
        os.makedirs(meta_dir, exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print("预测完成")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
