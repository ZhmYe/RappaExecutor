from typing import Any, Dict

import pandas as pd

from model.ABM.analytics.common import coerce_bool, safe_int
from model.ABM.analytics.constants import TRADER_TYPE_ORDER, TRADER_TYPES
from model.ABM.analytics.io import read_csv_frame


def build_order_dynamics_payload(abm_root, params: Dict[str, Any], selected_date: str = "") -> Dict[str, Any]:
    order_behavior = read_csv_frame(abm_root / "order_behavior.csv")
    order_book_reuse = read_csv_frame(abm_root / "order_book_reuse.csv")
    structural_params = extract_structural_params(params)
    normalized_date = str(selected_date or "").strip()
    return {
        "dailyDynamics": build_daily_dynamics(order_behavior, normalized_date),
        "intradayDepth": build_intraday_depth(order_book_reuse, structural_params, normalized_date),
    }


def extract_structural_params(params: Dict[str, Any]) -> Dict[str, Any]:
    abm_params = params.get("abm", {}) if isinstance(params.get("abm"), dict) else {}
    structural_params = (
        abm_params.get("structural_params", {})
        if isinstance(abm_params.get("structural_params"), dict)
        else {}
    )
    return structural_params


def build_daily_dynamics(df: pd.DataFrame, selected_date: str = "") -> Dict[str, Any]:
    empty_buy = [{"name": label, "data": []} for _, label in TRADER_TYPE_ORDER]
    empty_sell = [{"name": label, "data": []} for _, label in TRADER_TYPE_ORDER]
    if df.empty:
        return {"dates": [], "buyRatios": empty_buy, "sellRatios": empty_sell}

    working = df.copy()
    working["时间戳"] = pd.to_datetime(working["时间戳"], errors="coerce")
    working = working.dropna(subset=["时间戳"])
    if working.empty:
        return {"dates": [], "buyRatios": empty_buy, "sellRatios": empty_sell}

    working["date"] = working["时间戳"].dt.strftime("%Y-%m-%d")
    if selected_date:
        working = working[working["date"] == selected_date]
        if working.empty:
            return {"dates": [], "buyRatios": empty_buy, "sellRatios": empty_sell}

    working["交易类型"] = working["交易类型"].astype(str)
    working["总挂单数量"] = pd.to_numeric(working["总挂单数量"], errors="coerce").fillna(0.0)
    working["挂单中买单占比(数量)"] = pd.to_numeric(
        working["挂单中买单占比(数量)"], errors="coerce"
    ).fillna(0.0)

    records = []
    grouped = working.groupby(["date", "交易类型"], sort=True)
    for (date_value, trader_type), group in grouped:
        weight_sum = float(group["总挂单数量"].sum())
        if weight_sum > 0:
            weighted_value = (
                group["挂单中买单占比(数量)"] * group["总挂单数量"]
            ).sum() / weight_sum
        else:
            weighted_value = float(group["挂单中买单占比(数量)"].mean()) if not group.empty else 0.0
        buy_ratio = max(0.0, min(1.0, float(weighted_value)))
        records.append({"date": str(date_value), "trader_type": str(trader_type), "buy_ratio": round(buy_ratio, 4)})

    if not records:
        return {"dates": [], "buyRatios": empty_buy, "sellRatios": empty_sell}

    summary = pd.DataFrame(records)
    dates = sorted(summary["date"].astype(str).unique().tolist())
    pivot = summary.pivot(index="date", columns="trader_type", values="buy_ratio").fillna(0.0)
    pivot = pivot.reindex(index=dates, columns=TRADER_TYPES, fill_value=0.0)

    buy_ratios = []
    sell_ratios = []
    for trader_type, label in TRADER_TYPE_ORDER:
        buy_values = [round(float(value), 4) for value in pivot[trader_type].tolist()]
        sell_values = [round(max(0.0, min(1.0, 1.0 - value)), 4) for value in buy_values]
        buy_ratios.append({"name": label, "data": buy_values})
        sell_ratios.append({"name": label, "data": sell_values})

    return {"dates": dates, "buyRatios": buy_ratios, "sellRatios": sell_ratios}


def build_intraday_depth(df: pd.DataFrame, structural_params: Dict[str, Any], selected_date: str = "") -> Dict[str, Any]:
    empty_series = [{"name": label, "buy": [], "sell": []} for _, label in TRADER_TYPE_ORDER]
    if df.empty:
        return {"categories": [], "series": empty_series}

    working = df.copy()
    working["Timestamp"] = pd.to_datetime(working["Timestamp"], errors="coerce")
    working = working.dropna(subset=["Timestamp"])
    if working.empty:
        return {"categories": [], "series": empty_series}

    if selected_date:
        working = working[working["Timestamp"].dt.strftime("%Y-%m-%d") == selected_date]
        if working.empty:
            return {"categories": [], "series": empty_series}

    working["time_label"] = working["Timestamp"].dt.strftime("%H:%M")
    working["Volume"] = pd.to_numeric(working["Volume"], errors="coerce").fillna(0).astype(int)
    working["UserID"] = pd.to_numeric(working["UserID"], errors="coerce").fillna(-1).astype(int)
    working["is_buy"] = working["IsBuy"].apply(coerce_bool)
    working["trader_type"] = working["UserID"].apply(
        lambda user_id: map_user_to_trader_type(user_id, structural_params)
    )

    grouped = (
        working.groupby(["time_label", "trader_type", "is_buy"], sort=True)["Volume"]
        .sum()
        .reset_index()
    )
    categories = sorted(
        grouped["time_label"].astype(str).unique().tolist(),
        key=lambda item: pd.to_datetime(item, format="%H:%M", errors="coerce"),
    )

    series = []
    for trader_type, label in TRADER_TYPE_ORDER:
        trader_rows = grouped[grouped["trader_type"] == trader_type]
        buy_map = {
            str(row["time_label"]): int(row["Volume"])
            for _, row in trader_rows[trader_rows["is_buy"]].iterrows()
        }
        sell_map = {
            str(row["time_label"]): -int(row["Volume"])
            for _, row in trader_rows[~trader_rows["is_buy"]].iterrows()
        }
        series.append(
            {
                "name": label,
                "buy": [buy_map.get(category, 0) for category in categories],
                "sell": [sell_map.get(category, 0) for category in categories],
            }
        )

    return {"categories": categories, "series": series}


def map_user_to_trader_type(user_id: int, structural_params: Dict[str, Any]) -> str:
    n_ft = safe_int(structural_params.get("N_FT"), 0)
    n_lmt = safe_int(structural_params.get("N_LMT"), 0)
    n_smt = safe_int(structural_params.get("N_SMT"), 0)
    if 0 <= user_id < n_ft:
        return "Fundamental_Trader"
    if user_id < n_ft + n_lmt:
        return "Long_term_Momentum_Trader"
    if user_id < n_ft + n_lmt + n_smt:
        return "Short_term_Momentum_Trader"
    return "Noise_Trader"
