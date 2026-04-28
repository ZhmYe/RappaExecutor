"""
test.py

在不修改 simulate_optimization.py 的前提下，复用同一套调参/仿真逻辑，
并额外输出与 final.py 对齐的结果文件到：

    simulated_result/<CODE>/

输出文件（与 final.py 同名）：
- mid_price.csv
- order_book.csv
- order_book_reuse.csv
- match_result.csv
- multiple_market.csv

说明：
- 本脚本支持交互输入 CSV 文件名与 7 个结构参数（回车保留 config.py 默认）。
- 若环境变量 ABM_SKIP_STRUCT_PROMPT=1，则跳过结构参数询问。
"""

import config
import csv
import json
import os
import re
import sys
import pickle
import math
import pandas as pd
import numpy as np

from simulate_function import (
    init_config,
    calculate_fundamental_value,
    calibrate_parameters,
    create_instance,
    simulate_market,
    save_synthetic_data,
)
from loss_function import block_bootstrap
from save_function import save_order_book


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def parse_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    raw = str(raw).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return int(float(raw))


def _file_exists_candidates(name: str):
    name = (name or "").strip()
    candidates = [
        name,
        os.path.join(_BASE_DIR, name),
        os.path.join(os.getcwd(), name),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return os.path.abspath(c)
    return None


def resolve_input_csv():
    # argv 优先
    if len(sys.argv) > 1 and sys.argv[1].strip():
        found = _file_exists_candidates(sys.argv[1])
        if not found:
            raise FileNotFoundError(f"找不到输入文件: {sys.argv[1]}")
        return found

    env_csv = os.getenv("INPUT_CSV", "").strip()
    if env_csv:
        found = _file_exists_candidates(env_csv)
        if not found:
            raise FileNotFoundError(f"环境变量 INPUT_CSV 指向的文件不存在: {env_csv}")
        return found

    default_name = "600000.csv"
    while True:
        hint = input(f"请输入数据 CSV 文件名（ABM 目录或当前目录）[{default_name}]: ").strip() or default_name
        found = _file_exists_candidates(hint)
        if found:
            print(f"使用数据文件: {found}")
            return found
        print(f"未找到文件: {hint}，请重新输入。")


def prompt_structural_params(param_config: dict):
    skip = os.getenv("ABM_SKIP_STRUCT_PROMPT", "").strip().lower()
    if skip in ("1", "true", "yes"):
        return

    print("\n--- 结构参数（直接回车保留默认值）---")
    int_keys = ["N_FT", "N_LMT", "N_SMT", "N_NT", "S_FT"]
    for key in int_keys:
        cur = param_config[key]
        s = input(f"  {key} [{cur}]: ").strip()
        if not s:
            continue
        try:
            v = int(s)
            if v < 1:
                print(f"    {key} 须为 >=1 的整数，已忽略。")
                continue
            param_config[key] = v
        except ValueError:
            print(f"    {key} 不是合法整数，已忽略。")

    for key in ("ALPHA_L", "ALPHA_S"):
        cur = param_config[key]
        s = input(f"  {key} [{cur}]: ").strip()
        if not s:
            continue
        try:
            v = float(s)
            if v <= 0:
                print(f"    {key} 须为 >0，已忽略。")
                continue
            param_config[key] = v
        except ValueError:
            print(f"    {key} 不是合法浮点数，已忽略。")
    print("--- 结构参数设置完毕 ---\n")


def apply_structural_params_from_dict(param_config: dict, overrides: dict):
    if not isinstance(overrides, dict):
        return
    int_keys = ["N_FT", "N_LMT", "N_SMT", "N_NT", "S_FT", "VOLUME"]
    float_keys = [
        "ALPHA_L",
        "ALPHA_S",
        "MU_L",
        "SIGMA_L",
        "K1",
        "K2",
        "BETA_L",
        "BETA_S",
        "DELTA_NT",
        "THETA",
        "MU",
        "DELTA",
        "RHO",
        "GAMMA",
    ]

    for key in int_keys:
        if key not in overrides:
            continue
        try:
            v = int(overrides[key])
            if v >= 1:
                param_config[key] = v
            else:
                print(f"[WARN] 忽略非法结构参数 {key}={overrides[key]}（需>=1）")
        except Exception:
            print(f"[WARN] 忽略非法结构参数 {key}={overrides[key]}")

    for key in float_keys:
        if key not in overrides:
            continue
        try:
            v = float(overrides[key])
            param_config[key] = v
        except Exception:
            print(f"[WARN] 忽略非法结构参数 {key}={overrides[key]}")


def load_structural_params_from_env() -> dict:
    raw_json = os.getenv("ABM_STRUCT_PARAMS_JSON", "").strip()
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict):
                return parsed
            print("[WARN] ABM_STRUCT_PARAMS_JSON 不是对象，已忽略")
        except Exception as exc:
            print(f"[WARN] ABM_STRUCT_PARAMS_JSON 解析失败，已忽略: {exc}")

    json_path = os.getenv("ABM_STRUCT_PARAMS_FILE", "").strip()
    if json_path:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                parsed = json.load(f)
            if isinstance(parsed, dict):
                return parsed
            print("[WARN] ABM_STRUCT_PARAMS_FILE 内容不是对象，已忽略")
        except Exception as exc:
            print(f"[WARN] ABM_STRUCT_PARAMS_FILE 读取失败，已忽略: {exc}")
    return {}


def load_model_params_from_env() -> dict:
    json_path = os.getenv("ABM_MODEL_PARAMS_FILE", "").strip()
    if json_path:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                parsed = json.load(f)
            if isinstance(parsed, dict):
                return parsed
            print("[WARN] ABM_MODEL_PARAMS_FILE 内容不是对象，已忽略")
        except Exception as exc:
            print(f"[WARN] ABM_MODEL_PARAMS_FILE 读取失败，已忽略: {exc}")

    raw_json = os.getenv("ABM_MODEL_PARAMS_JSON", "").strip()
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict):
                return parsed
            print("[WARN] ABM_MODEL_PARAMS_JSON 不是对象，已忽略")
        except Exception as exc:
            print(f"[WARN] ABM_MODEL_PARAMS_JSON 解析失败，已忽略: {exc}")
    return {}


def apply_model_params(param_config: dict, payload: dict):
    if not isinstance(payload, dict):
        return
    structural = payload.get("structural_params", {}) if isinstance(payload.get("structural_params", {}), dict) else {}
    calibrated = payload.get("calibrated_params", {}) if isinstance(payload.get("calibrated_params", {}), dict) else {}
    apply_structural_params_from_dict(param_config, structural)
    apply_structural_params_from_dict(param_config, calibrated)


def infer_code(input_path: str, df: pd.DataFrame) -> str:
    # 优先从 stockid 列推断
    if "stockid" in df.columns:
        uniq = df["stockid"].dropna().astype(str).unique()
        if len(uniq) == 1:
            return uniq[0]
        if len(uniq) > 1:
            # 多股票混合时取第一个，但提示
            print(f"[WARN] stockid 存在多个值，仅使用第一个: {uniq[0]}")
            return uniq[0]

    # 退化：从文件名提取数字
    base = os.path.basename(input_path)
    m = re.search(r"(\d{6})", base)
    if m:
        return m.group(1)
    return "UNKNOWN"


def save_pickle(params, filename):
    out_dir = os.path.dirname(filename)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(filename, "wb") as f:
        pickle.dump(params, f)


def write_final_style_outputs(market, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)

    # mid_price.csv
    mid_path = os.path.join(out_dir, "mid_price.csv")
    with open(mid_path, mode="w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Timestamp", "Price"])
        for ts, price in market.mid_price:
            w.writerow([ts, price])

    # order_book.csv
    ob_path = os.path.join(out_dir, "order_book.csv")
    with open(ob_path, mode="w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Timestamp", "OrderBook"])
        for ts, ob in market.orders:
            w.writerow([ts, ob])

    # order_book_reuse.csv
    ob_reuse_path = os.path.join(out_dir, "order_book_reuse.csv")
    save_order_book(ob_reuse_path, market.orders)

    # match_result.csv
    match_path = os.path.join(out_dir, "match_result.csv")
    with open(match_path, mode="w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Timestamp", "MatchResult"])
        for ts, mr in market.match_result:
            w.writerow([ts, mr])

    # multiple_market.csv
    mm_path = os.path.join(out_dir, "multiple_market.csv")
    with open(mm_path, mode="w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["Timestamp"]
            + [
                "buy1", "sale1", "bc1", "sc1",
                "buy2", "sale2", "bc2", "sc2",
                "buy3", "sale3", "bc3", "sc3",
                "buy4", "sale4", "bc4", "sc4",
                "buy5", "sale5", "bc5", "sc5",
                "buy6", "sale6", "bc6", "sc6",
                "buy7", "sale7", "bc7", "sc7",
                "buy8", "sale8", "bc8", "sc8",
                "buy9", "sale9", "bc9", "sc9",
                "buy10", "sale10", "bc10", "sc10",
            ]
        )
        for ts, mm in market.multiple_market:
            # mm 预期是长度 40 的 list（十档*4列）
            w.writerow([ts] + (mm if isinstance(mm, list) else list(mm)))

    print(f"[OK] final-style 输出已写入: {out_dir}")


def write_trader_demand_csv(trader_demand_rows, out_dir: str):
    """
    输出与 final.py 对齐的 trader_demand.csv：
    Timestamp + 四类交易者需求
    """
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "trader_demand.csv")
    df = pd.DataFrame(trader_demand_rows)
    if len(df) == 0:
        df = pd.DataFrame(
            columns=[
                "Timestamp",
                "Fundamental_Trader",
                "Long_term_Momentum_Trader",
                "Short_term_Momentum_Trader",
                "Noise_Trader",
            ]
        )
    else:
        # 强制列顺序
        df = df[
            [
                "Timestamp",
                "Fundamental_Trader",
                "Long_term_Momentum_Trader",
                "Short_term_Momentum_Trader",
                "Noise_Trader",
            ]
        ]
    df.to_csv(path, index=False)
    print(f"[OK] 数据已写入 {path}")


def write_order_behavior_csv(market, trader_index, out_dir: str):
    """
    输出与 final.py 的 order_behavior.csv“字段风格”一致的统计结果。

    注意：final.py 是从 order_book.csv 的字符串反解析订单；
    这里直接使用 market.orders 中的 Order 对象，避免正则解析不稳定。
    """
    os.makedirs(out_dir, exist_ok=True)

    trader_type = [
        "Fundamental_Trader",
        "Long_term_Momentum_Trader",
        "Short_term_Momentum_Trader",
        "Noise_Trader",
    ]

    def id_to_type(trader_id):
        if trader_id >= trader_index[0] and trader_id < trader_index[1]:
            return trader_type[0]
        if trader_id >= trader_index[1] and trader_id < trader_index[2]:
            return trader_type[1]
        if trader_id >= trader_index[2] and trader_id < trader_index[3]:
            return trader_type[2]
        return trader_type[3]

    # 拉平订单簿为记录
    records = []
    for ts, order_list in market.orders:
        for o in (order_list or []):
            records.append(
                {
                    "timestamp": ts,
                    "account_type": id_to_type(getattr(o, "trader_id", -1)),
                    "direction": "buy" if getattr(o, "is_buy", False) else "sell",
                    "quantity": int(getattr(o, "quantity", 0) or 0),
                }
            )

    out_path = os.path.join(out_dir, "order_behavior.csv")
    if not records:
        empty = pd.DataFrame(
            columns=[
                "时间戳",
                "交易类型",
                "总挂单数量",
                "总挂单笔数",
                "买单数量",
                "买单笔数",
                "挂单中买单占比(数量)",
                "挂单中买单占比(笔数)",
                "挂单量占比",
            ]
        )
        empty.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"[OK] 数据已写入 {out_path}")
        return

    df = pd.DataFrame(records)
    # 每个时间点总挂单量（数量口径）
    total_by_timestamp = df.groupby("timestamp")["quantity"].sum().to_dict()

    grouped = (
        df.groupby(["timestamp", "account_type"])
        .agg(total_quantity=("quantity", "sum"), total_count=("quantity", "count"))
        .reset_index()
    )

    buy_stats = (
        df[df["direction"] == "buy"]
        .groupby(["timestamp", "account_type"])
        .agg(buy_quantity=("quantity", "sum"), buy_count=("quantity", "count"))
        .reset_index()
    )

    grouped = grouped.merge(buy_stats, on=["timestamp", "account_type"], how="left")
    grouped["buy_quantity"] = grouped["buy_quantity"].fillna(0).astype(int)
    grouped["buy_count"] = grouped["buy_count"].fillna(0).astype(int)

    grouped["buy_ratio_quantity"] = (grouped["buy_quantity"] / grouped["total_quantity"]).fillna(0)
    grouped["buy_ratio_count"] = (grouped["buy_count"] / grouped["total_count"]).fillna(0)

    def order_volume_ratio(row):
        total = total_by_timestamp.get(row["timestamp"], 0)
        if total <= 0:
            return 0.0
        return float(row["total_quantity"]) / float(total)

    grouped["order_volume_ratio"] = grouped.apply(order_volume_ratio, axis=1)

    # 补齐所有 timestamp x trader_type 组合（与 final.py 一致）
    unique_timestamps = sorted(df["timestamp"].unique())
    all_combinations = [(ts, t) for ts in unique_timestamps for t in trader_type]
    comb_df = pd.DataFrame(all_combinations, columns=["timestamp", "account_type"])
    summary = comb_df.merge(grouped, on=["timestamp", "account_type"], how="left")

    summary["total_quantity"] = summary["total_quantity"].fillna(0).astype(int)
    summary["total_count"] = summary["total_count"].fillna(0).astype(int)
    summary["buy_quantity"] = summary["buy_quantity"].fillna(0).astype(int)
    summary["buy_count"] = summary["buy_count"].fillna(0).astype(int)
    summary["buy_ratio_quantity"] = summary["buy_ratio_quantity"].fillna(0).round(4)
    summary["buy_ratio_count"] = summary["buy_ratio_count"].fillna(0).round(4)
    summary["order_volume_ratio"] = summary["order_volume_ratio"].fillna(0).round(4)

    # 重命名为中文列名（final.py 风格）
    summary = summary.rename(
        columns={
            "timestamp": "时间戳",
            "account_type": "交易类型",
            "total_quantity": "总挂单数量",
            "total_count": "总挂单笔数",
            "buy_quantity": "买单数量",
            "buy_count": "买单笔数",
            "buy_ratio_quantity": "挂单中买单占比(数量)",
            "buy_ratio_count": "挂单中买单占比(笔数)",
            "order_volume_ratio": "挂单量占比",
        }
    )
    summary = summary[
        [
            "时间戳",
            "交易类型",
            "总挂单数量",
            "总挂单笔数",
            "买单数量",
            "买单笔数",
            "挂单中买单占比(数量)",
            "挂单中买单占比(笔数)",
            "挂单量占比",
        ]
    ].sort_values("时间戳")

    summary.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[OK] 数据已写入 {out_path}")

def write_kline_ohlcv_from_mid_price_and_order_reuse(out_dir: str) -> None:
    """
    生成用于 K 线展示的合成 OHLCV（日频）。

    - OHLC 来自 simulated_result/<code>/mid_price.csv 的 Price
    - Volume 用 simulated_result/<code>/order_book_reuse.csv 的日度挂单量总和作为成交量近似
    """
    mid_path = os.path.join(out_dir, "mid_price.csv")
    ob_reuse_path = os.path.join(out_dir, "order_book_reuse.csv")

    if not os.path.exists(mid_path):
        print(f"[WARN] mid_price.csv missing, skip kline generation: {mid_path}")
        return

    mid_df = pd.read_csv(mid_path)
    mid_df["Timestamp"] = pd.to_datetime(mid_df["Timestamp"], errors="coerce")
    mid_df = mid_df.dropna(subset=["Timestamp"]).sort_values("Timestamp")
    mid_df["date"] = mid_df["Timestamp"].dt.strftime("%Y-%m-%d")

    daily_price = (
        mid_df.groupby("date")["Price"]
        .agg(open="first", high="max", low="min", close="last")
        .reset_index()
    )

    # Volume proxy: total order volume per day
    daily_price["Volume"] = 0.0
    if os.path.exists(ob_reuse_path):
        ob_df = pd.read_csv(ob_reuse_path)
        ob_df["Timestamp"] = pd.to_datetime(ob_df["Timestamp"], errors="coerce")
        ob_df = ob_df.dropna(subset=["Timestamp"])
        ob_df["date"] = ob_df["Timestamp"].dt.strftime("%Y-%m-%d")
        if "Volume" in ob_df.columns:
            ob_df["Volume"] = pd.to_numeric(ob_df["Volume"], errors="coerce").fillna(0)
            vol_daily = ob_df.groupby("date")["Volume"].sum()
            daily_price["Volume"] = daily_price["date"].map(vol_daily).fillna(0.0).astype(float)

    # ECharts candlestick 用 value: [open, close, low, high]，这里只保证字段齐全即可
    daily_price = daily_price.rename(columns={"date": "Timestamp"})
    daily_price = daily_price[["Timestamp", "open", "high", "low", "close", "Volume"]]
    daily_price.columns = ["Timestamp", "Open", "High", "Low", "Close", "Volume"]

    out_path = os.path.join(out_dir, "kline_ohlcv.csv")
    daily_price.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[OK] kline_ohlcv 已写入: {out_path}")


def simulate_market_full(traders, exchange, market, prices, dates, trader_type, cfg, trader_index):
    """
    在 simulate_function.simulate_market 的基础上扩展：
    - 返回 market（包含 mid_price/order_book/match_result/multiple_market）
    - 同时记录 trader_demand（与 final.py 逻辑对齐）
    """
    # 开盘
    timestamp = dates[0]
    all_match_result = []
    open_price = round(prices[0], 2)
    open_mid_price = round(prices[0], 2)
    open_market = exchange.order_book_to_market(open_mid_price, 10, 0.01)
    market.update_simulation(exchange.orders, all_match_result, open_price, open_mid_price, open_market, timestamp)

    simulation_step = 0
    trader_demand_rows = []

    while simulation_step < len(dates) - 1:
        timestamp = dates[simulation_step + 1]

        all_limit_orders = []
        all_market_orders = []
        all_cancel_orders = []
        all_match_result = []

        for trader in traders:
            current_price = market.price_trend[-1][1]
            match_result = market.match_result[-1][1]
            current_mid_price = market.mid_price[-1][1]

            for match_order in match_result:
                if trader.trader_id == match_order[0].trader_id:
                    trader.update_state(match_order[0], match_order[2], match_order[3])
                if trader.trader_id == match_order[1].trader_id:
                    trader.update_state(match_order[1], match_order[2], match_order[3])

            if trader.trader_type == trader_type[0]:
                market_orders = trader.trading_function(cfg["STOCK_SYMBOL"], timestamp, simulation_step, current_mid_price)
                all_market_orders.extend(market_orders)

            if trader.trader_type == trader_type[1]:
                sample = np.random.randn()
                price_distance = np.exp(cfg["MU_L"] + cfg["SIGMA_L"] * sample)
                cancel_orders, market_orders, limit_orders = trader.trading_function(
                    cfg["STOCK_SYMBOL"], timestamp, current_mid_price, price_distance
                )
                all_cancel_orders.extend(cancel_orders)
                all_market_orders.extend(market_orders)
                all_limit_orders.extend(limit_orders)

            if trader.trader_type == trader_type[2]:
                sample = np.random.randn()
                price_distance = np.exp(cfg["MU_L"] + cfg["SIGMA_L"] * sample)
                cancel_orders, market_orders, limit_orders = trader.trading_function(
                    cfg["STOCK_SYMBOL"], timestamp, current_mid_price, price_distance
                )
                all_cancel_orders.extend(cancel_orders)
                all_market_orders.extend(market_orders)
                all_limit_orders.extend(limit_orders)

            if trader.trader_type == trader_type[3]:
                sample = np.random.randn()
                price_distance = np.exp(cfg["MU_L"] + cfg["SIGMA_L"] * sample)
                cancel_orders, market_orders, limit_orders = trader.trading_function(
                    cfg["STOCK_SYMBOL"], timestamp, current_mid_price, price_distance
                )
                all_cancel_orders.extend(cancel_orders)
                all_market_orders.extend(market_orders)
                all_limit_orders.extend(limit_orders)

        for cancel_order_id in all_cancel_orders:
            exchange.del_order(cancel_order_id)

        for market_order in all_market_orders:
            market_matched_orders = exchange.add_and_match_market_order(market_order)
            all_match_result.extend(market_matched_orders)

        for limit_order in all_limit_orders:
            limit_order_id = exchange.add_order(limit_order)
            traders[limit_order.trader_id].orders.append(limit_order_id)

        limit_matched_orders, mean_price = exchange.match_orders_in_call_auction()
        if mean_price is None:
            current_price = market.price_trend[-1][1]
            if len(all_match_result) == 0:
                mean_price = current_price
            else:
                price_sum = sum([m[3] for m in all_match_result])
                mean_price = round(price_sum / len(all_match_result), 2)

        all_match_result.extend(limit_matched_orders)

        mid_price = exchange.calculate_midprice()
        if mid_price is None:
            mid_price = market.mid_price[-1][1]

        multiple_market = exchange.order_book_to_market(mid_price, 10, 0.01)
        market.update_simulation(exchange.orders, all_match_result, mean_price, mid_price, multiple_market, timestamp)

        # -------- trader_demand（对齐 final.py）--------
        # 注意：这里只使用每类的“第一个” trader 作为代表（final.py 同样这样做）
        try:
            ft = traders[trader_index[0]]
            lmt = traders[trader_index[1]]
            smt = traders[trader_index[2]]
            nt = traders[trader_index[3]]

            FT_Demand = (ft.Theta + ft.Mu) * cfg["N_FT"]
            LMT_Demand = (lmt.Theta + lmt.Mu) * cfg["N_LMT"]
            SMT_Demand = (smt.Theta + smt.Mu) * cfg["N_SMT"]
            NT_Demand = (nt.Theta + nt.Mu) * cfg["N_NT"]

            # 方向符号（final.py 逻辑）
            if ft.fundamental_value[simulation_step] - ft.price_trend < 0:
                FT_Demand = -FT_Demand
            if getattr(lmt, "Mt", 0) < 0:
                LMT_Demand = -LMT_Demand
            if getattr(smt, "Mt", 0) < 0:
                SMT_Demand = -SMT_Demand
        except Exception:
            FT_Demand = 0
            LMT_Demand = 0
            SMT_Demand = 0
            NT_Demand = 0

        trader_demand_rows.append(
            {
                "Timestamp": timestamp,
                "Fundamental_Trader": FT_Demand,
                "Long_term_Momentum_Trader": LMT_Demand,
                "Short_term_Momentum_Trader": SMT_Demand,
                "Noise_Trader": NT_Demand,
            }
        )

        simulation_step += 1

    return market, trader_demand_rows


def main():
    trader_type = ["Fundamental_Trader", "Long_term_Momentum_Trader", "Short_term_Momentum_Trader", "Noise_Trader"]

    params_index = ["MU_L", "DELTA_NT", "K1", "K2", "BETA_L", "BETA_S"]
    param_bounds = {
        "MU_L": (0.1, 5.0),
        "DELTA_NT": (0.01, 5.0),
        "K1": (0.0001, 5.0),
        "K2": (0.0001, 5.0),
        "BETA_L": (0.0001, 5.0),
        "BETA_S": (0.0001, 5.0),
    }

    param_config = init_config(config)

    input_file = resolve_input_csv()

    df = pd.read_csv(input_file)
    max_rows = parse_int_env("MAX_ROWS", 0)
    if max_rows > 0:
        df = df.head(max_rows)

    # 交互设置结构参数（写进 param_config，直接影响仿真）
    prompt_structural_params(param_config)
    # 额外支持从参数文件/JSON注入（前端/服务调用）
    apply_structural_params_from_dict(param_config, load_structural_params_from_env())
    # 若提供离线调参产物，则直接加载参数并跳过在线调参。
    model_payload = load_model_params_from_env()
    use_precalibrated = bool(model_payload)
    if use_precalibrated:
        apply_model_params(param_config, model_payload)
        print("[INFO] 已加载离线参数，当前运行模式：直接仿真（跳过调参）")

    date_col = "date" if "date" in df.columns else "Time"
    if date_col not in df.columns:
        raise ValueError("输入文件必须包含时间列：date 或 Time")
    if "close" not in df.columns:
        raise ValueError("输入文件必须包含价格列：close。若原始列名为 Price/price/Close，请先重命名为 close。")
    prices = df["close"].tolist()
    dates = df[date_col].tolist()

    # 十档行情仅在在线调参时用于 loss 计算；预加载参数模式只需 Time/date + close。
    market_cols = [
        "buy1", "sale1", "bc1", "sc1", "buy2", "sale2", "bc2", "sc2", "buy3", "sale3", "bc3", "sc3",
        "buy4", "sale4", "bc4", "sc4", "buy5", "sale5", "bc5", "sc5", "buy6", "sale6", "bc6", "sc6",
        "buy7", "sale7", "bc7", "sc7", "buy8", "sale8", "bc8", "sc8", "buy9", "sale9", "bc9", "sc9",
        "buy10", "sale10", "bc10", "sc10",
    ]
    true_markets = None
    missing_market_cols = [col for col in market_cols if col not in df.columns]
    if not use_precalibrated:
        if missing_market_cols:
            raise ValueError(
                "在线调参模式需要十档行情字段；缺失字段: "
                + ", ".join(missing_market_cols)
                + "。如果只有时间和价格列，请使用 abm.mode=precalibrated 并提供离线 model_params.json。"
            )
        true_markets = df[market_cols].values.tolist()

    code = infer_code(input_file, df)
    print(f"股票代码 CODE: {code}")

    fundamental_value = calculate_fundamental_value(prices)
    if use_precalibrated:
        final_config = param_config.copy()
        loss_history = []
        print(f"simulation config -> rows: {len(df)}, mode: preload_params")
    else:
        bootstrap_samples = parse_int_env("BOOTSTRAP_SAMPLES", 1000)
        cof_dict = block_bootstrap(prices, 240, bootstrap_samples)
        print(f"hill: {cof_dict['hill']}, vol: {cof_dict['vol']}, acf: {cof_dict['acf']}, square_acf: {cof_dict['sacf']}")

        initial = {
            "true_prices": prices,
            "true_markets": true_markets,
            "cof_dict": cof_dict,
            "fundamental_value": fundamental_value,
            "dates": dates,
            "trader_type": trader_type,
            "params_index": params_index,
            "config": param_config,
            "seed_count": parse_int_env("SEED_COUNT", 3),
            "base_seed": parse_int_env("BASE_SEED", 2026),
            "param_bounds": param_bounds,
            "patience": parse_int_env("PATIENCE", 30),
        }

        learning_rate = float(os.getenv("LEARNING_RATE", "0.01"))
        epoch = parse_int_env("EPOCH", 100)
        epsilon = float(os.getenv("EPSILON", "0.001"))
        print(
            f"training config -> epoch: {epoch}, lr: {learning_rate}, epsilon: {epsilon}, "
            f"bootstrap_samples: {bootstrap_samples}, rows: {len(df)}"
        )

        final_config, loss_history = calibrate_parameters(initial, learning_rate, epsilon, epoch)

    output_root = os.getenv("ABM_OUTPUT_ROOT", "simulated_result").strip() or "simulated_result"
    os.makedirs(output_root, exist_ok=True)

    # ========== 保存调参结果（与 simulate_optimization.py 保持一致风格） ==========
    loss_path = os.path.join(output_root, "loss_result.csv")
    with open(loss_path, mode="w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Iteration", "Loss"])
        for i, l in enumerate(loss_history):
            w.writerow([i, l])

    params_path = os.path.join(output_root, "params_result.csv")
    with open(params_path, mode="w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Params", "Value"])
        for k in params_index:
            w.writerow([k, final_config[k]])

    bounds_path = os.path.join(output_root, "param_bounds.csv")
    with open(bounds_path, mode="w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Params", "Lower", "Upper"])
        for k in params_index:
            lo, hi = param_bounds[k]
            w.writerow([k, lo, hi])

    # 完整参数包（供后续复用）
    model_params = final_config.copy()
    model_params["timestamps"] = dates
    model_params["fundamental_value"] = fundamental_value
    model_params["open_price"] = round(prices[0], 2) if prices else None
    model_path = os.path.join(output_root, "model_params.tsf")
    save_pickle(model_params, model_path)

    # ========== 用最优参数跑一次仿真并输出 ==========
    # trader_index：用于 demand 与类型映射（与 final.py 一致）
    trader_index = [
        0,
        int(final_config["N_FT"]),
        int(final_config["N_FT"]) + int(final_config["N_LMT"]),
        int(final_config["N_FT"]) + int(final_config["N_LMT"]) + int(final_config["N_SMT"]),
    ]

    traders, exchange, market = create_instance(final_config, fundamental_value, prices[0])
    # 用扩展仿真，额外得到 trader_demand
    market, trader_demand_rows = simulate_market_full(
        traders, exchange, market, prices, dates, trader_type, final_config, trader_index
    )

    # 现有 synthetic_data 输出（兼容老流程）
    save_synthetic_data(market, os.path.join(output_root, "synthetic_data"))

    # final.py 对齐输出：simulated_result/<CODE>/
    final_dir = os.path.join(output_root, str(code))
    write_final_style_outputs(market, final_dir)
    write_trader_demand_csv(trader_demand_rows, final_dir)
    write_order_behavior_csv(market, trader_index, final_dir)
    write_kline_ohlcv_from_mid_price_and_order_reuse(final_dir)

    # 训练摘要
    best_loss = min(loss_history) if loss_history else None
    log_path = os.path.join(output_root, "train_log.txt")
    struct_keys = ["N_FT", "N_LMT", "N_SMT", "N_NT", "S_FT", "ALPHA_L", "ALPHA_S"]
    with open(log_path, mode="w", encoding="utf-8") as f:
        f.write("Start Simulation and Training\n")
        f.write(f"Run mode: {'preload_params' if use_precalibrated else 'online_calibration'}\n")
        f.write(f"Input file: {input_file}\n")
        if use_precalibrated:
            f.write(f"Loaded model params file: {os.getenv('ABM_MODEL_PARAMS_FILE', '')}\n")
        else:
            f.write(
                f"Epoch: {epoch}, Learning rate: {learning_rate}, Epsilon: {epsilon}, "
                f"Bootstrap samples: {bootstrap_samples}, Seed count: {initial['seed_count']}\n"
            )
        f.write(f"Rows used: {len(df)}\n")
        f.write("Structural params used:\n")
        for k in struct_keys:
            f.write(f"  {k}: {final_config.get(k)}\n")
        if best_loss is not None:
            f.write(f"Best loss: {best_loss}\n")
        f.write(f"Final calibrated params (MU_L,...): { {k: final_config.get(k) for k in params_index} }\n")
        f.write(f"Final-style output dir: {final_dir}\n")
        f.write("Finish Simulation and Training\n")

    print(f"[OK] 完成：已输出 {output_root} 与 {final_dir}")


if __name__ == "__main__":
    main()
