from typing import Any, Dict

import pandas as pd

from model.ABM.analytics.common import (
    average_scores,
    pct_diff_score,
    relative_similarity_score,
    round_or_none,
    safe_float,
    unit_interval_score,
    zero_target_score,
)
from model.ABM.analytics.constants import PERFORMANCE_TABLE_ROWS, RADAR_INDICATORS
from model.ABM.analytics.io import read_csv_frame


def build_performance_comparison_payload(abm_root, selected_model: str = "ABM") -> Dict[str, Any]:
    all_metrics_df = read_csv_frame(abm_root / "cal_all_compare_metrics.csv")
    diff_metrics_df = read_csv_frame(abm_root / "cal_compare_diff_metrics.csv")
    level_metrics_df = read_csv_frame(abm_root / "cal_compare_level_metrics.csv")

    actual_model = resolve_available_model(all_metrics_df, selected_model)
    all_metrics_row = pick_model_row(all_metrics_df, actual_model)
    diff_metrics_row = pick_model_row(diff_metrics_df, actual_model)
    level_metrics_row = pick_model_row(level_metrics_df, actual_model)

    return {
        "selectedModel": actual_model,
        "tableData": build_performance_table_data(all_metrics_row),
        "radarData": build_performance_radar_data(level_metrics_row, diff_metrics_row, all_metrics_row, actual_model),
    }


def resolve_available_model(df: pd.DataFrame, selected_model: str) -> str:
    requested = normalize_model_name(selected_model)
    if df.empty or "model" not in df.columns:
        return requested

    available = [normalize_model_name(value) for value in df["model"].dropna().astype(str).tolist()]
    if requested in available:
        return requested
    if "ABM" in available:
        return "ABM"
    return available[0] if available else requested


def normalize_model_name(model_name: str) -> str:
    value = str(model_name or "").strip()
    if not value:
        return "ABM"
    canonical = {
        "ABM": "ABM",
        "GBM": "GBM",
        "GAN": "GAN",
        "VRNN": "VRNN",
        "TIMEGAN": "TimeGAN",
    }
    return canonical.get(value.upper(), value)


def pick_model_row(df: pd.DataFrame, model_name: str) -> Dict[str, Any]:
    if df.empty:
        raise ValueError("performance comparison source file is empty")
    if "model" in df.columns:
        matched = df[df["model"].astype(str).str.upper() == model_name.upper()]
        if not matched.empty:
            return matched.iloc[0].to_dict()
    return df.iloc[0].to_dict()


def build_performance_table_data(metrics_row: Dict[str, Any]) -> list[Dict[str, Any]]:
    rows = []
    for item in PERFORMANCE_TABLE_ROWS:
        true_value = performance_true_value(metrics_row, item)
        sim_value = safe_float(metrics_row.get(item.get("sim_key")))
        if sim_value is None:
            continue
        diff_value = performance_diff_value(true_value, sim_value, item.get("diff_mode", "none"))
        rows.append(
            {
                "indicator": item["indicator"],
                "trueData": round_or_none(true_value, 6) if true_value is not None else None,
                "abmSynthesis": round_or_none(sim_value, 6),
                "diff": round_or_none(diff_value, 4) if diff_value is not None else None,
            }
        )
    return rows


def build_performance_radar_data(
    level_metrics_row: Dict[str, Any],
    diff_metrics_row: Dict[str, Any],
    all_metrics_row: Dict[str, Any],
    selected_model: str,
) -> Dict[str, Any]:
    risk_return = average_scores(
        [
            relative_similarity_score(level_metrics_row.get("mean_true"), level_metrics_row.get("mean_sim")),
            pct_diff_score(diff_metrics_row.get("annual_vol_diff_pct")),
        ]
    )
    distribution = average_scores(
        [
            relative_similarity_score(level_metrics_row.get("std_true"), level_metrics_row.get("std_sim")),
            relative_similarity_score(level_metrics_row.get("cv_true"), level_metrics_row.get("cv_sim")),
            relative_similarity_score(level_metrics_row.get("kurt_true"), level_metrics_row.get("kurt_sim")),
            relative_similarity_score(level_metrics_row.get("skew_true"), level_metrics_row.get("skew_sim")),
        ]
    )
    trajectory = average_scores(
        [
            pct_diff_score(diff_metrics_row.get("hill_diff_pct")),
            zero_target_score(diff_metrics_row.get("acf_abs_mean_diff")),
            zero_target_score(diff_metrics_row.get("mse")),
        ]
    )
    price_volume = average_scores(
        [
            unit_interval_score(all_metrics_row.get("pearson_corr")),
            relative_similarity_score(1.0, all_metrics_row.get("depth_ratio")),
        ]
    )

    return {
        "indicator": RADAR_INDICATORS,
        "series": [
            {"name": "真实数据(True基准)", "value": [100.0, 100.0, 100.0, 100.0]},
            {
                "name": f"{normalize_model_name(selected_model)}合成",
                "value": [
                    round(risk_return, 2),
                    round(distribution, 2),
                    round(trajectory, 2),
                    round(price_volume, 2),
                ],
            },
        ],
    }


def performance_true_value(metrics_row: Dict[str, Any], item: Dict[str, Any]):
    if "true_value" in item:
        return item["true_value"]
    true_key = item.get("true_key")
    if not true_key:
        return None
    return safe_float(metrics_row.get(true_key))


def performance_diff_value(true_value, sim_value, diff_mode: str):
    if diff_mode == "none":
        return None
    if diff_mode == "absolute":
        baseline = 0.0 if true_value is None else true_value
        return sim_value - baseline
    if true_value is None:
        return None
    baseline = abs(float(true_value))
    if baseline < 1e-12:
        return sim_value - true_value
    return (sim_value - true_value) / baseline * 100.0
