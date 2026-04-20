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
from typing import Dict, List, Tuple

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
    p.add_argument("--method", default="auto", choices=["auto", "kalman_rw", "holt", "mean_reversion", "abm_fv"])
    p.add_argument("--horizon", type=int, default=22, help="Forecast steps (default: 22 business days)")
    p.add_argument("--tune", default="auto", choices=["auto", "off"], help="Auto tune params or not")
    p.add_argument("--output_csv", default="", help="Reserved; output is fixed to predict_fv.csv")
    p.add_argument("--meta_json", default="", help="Optional meta info output path")
    p.add_argument("--fv_next", type=float, default=np.nan, help="方案abm_fv首日FV输入值")
    p.add_argument("--abm_rounds", type=int, default=5, help="方案abm_fv每日ABM仿真轮数")
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
        while True:
            raw_fv = input("请输入 next_day FV 值（例如 8.75）: ").strip()
            try:
                args.fv_next = float(raw_fv)
                break
            except Exception:
                print("FV输入无效，请输入数字。")
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

    times, prices, time_col, price_col = load_series(input_csv)
    y = prices.astype(float).values

    if args.method == "abm_fv":
        steps_per_day = estimate_steps_per_day(input_csv, time_col)
        pred = run_scheme5_abm_fv(
            prices=y,
            fv_next=args.fv_next,
            horizon=args.horizon,
            steps_per_day=steps_per_day,
            abm_rounds=args.abm_rounds,
        )
        best = BestConfig(method="abm_fv", params={"fv_next": float(args.fv_next)}, cv_mae=float("nan"))
    else:
        best = auto_select_and_tune(y, args.method, args.tune)
        pred = forecast_anchor(best.method, y, horizon=args.horizon, params=best.params).astype(float)

    future_times = build_future_time_index(pd.Timestamp(times.iloc[-1]), args.horizon)
    out_df = pd.DataFrame({
        "Forecast_Time": future_times,
        "Predicted_Price": pred,
    })

    # Add probability columns for risk/threshold visualization.
    # Convention: use Prob_Drop_Xpct = P(Price <= last_close*(1-X)) under Normal(mean=pred, sd=sigma).
    drop_levels = (0.03, 0.05, 0.10)  # 3%/5%/10% downside
    last_close = float(y[-1]) if len(y) > 0 else np.nan

    sigma = np.nan
    if np.isfinite(best.cv_mae) and best.cv_mae > 0:
        # Under Normal(0, sigma): MAE = sigma * sqrt(2/pi)  =>  sigma = MAE * sqrt(pi/2)
        sigma = float(best.cv_mae) * np.sqrt(np.pi / 2.0) * np.sqrt(max(1, args.horizon))
    else:
        # Fallback: estimate MAE from naive 1-step "random walk" errors.
        if len(y) >= 2:
            naive_errors = np.abs(y[1:] - y[:-1]).astype(float)
            mae = float(np.nanmean(naive_errors))
            if np.isfinite(mae) and mae > 0:
                sigma = mae * np.sqrt(np.pi / 2.0) * np.sqrt(max(1, args.horizon))

    for level in drop_levels:
        threshold = last_close * (1.0 - level)
        col = f"Prob_Drop_{int(level * 100)}pct"
        if not np.isfinite(sigma) or sigma <= 0:
            out_df[col] = np.nan
        else:
            z = (threshold - pred) / sigma  # vectorized for each horizon step
            out_df[col] = norm.cdf(z)

    # Convenience for UI gauge: use 10% drop probability as crash probability.
    out_df["Crash_Prob"] = out_df["Prob_Drop_10pct"]

    out_csv = args.output_csv or "predict_fv.csv"
    out_dir = os.path.dirname(out_csv)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    out_df.to_csv(out_csv, index=False, encoding="utf-8-sig")

    meta = {
        "input_csv": input_csv,
        "detected_time_col": time_col,
        "detected_price_col": price_col,
        "effective_points": int(len(y)),
        "method": best.method,
        "params": best.params,
        "cv_mae": best.cv_mae,
        "last_close": last_close,
        "assumed_sigma": float(sigma) if np.isfinite(sigma) else None,
        "drop_levels": list(drop_levels),
        "prob_definition": "Prob_Drop_Xpct = P(Price <= last_close*(1-X)) under Normal(mean=pred, sd=assumed_sigma)",
        "horizon": args.horizon,
        "output_csv": out_csv,
    }
    if args.method == "abm_fv":
        meta["abm_rounds"] = int(args.abm_rounds)
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
