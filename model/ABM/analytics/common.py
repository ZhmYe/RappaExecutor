from typing import Any

import pandas as pd


def safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any):
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def round_or_none(value: Any, digits: int = 6):
    if pd.isna(value):
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "t"}


def average_scores(values: list) -> float:
    valid_values = [float(value) for value in values if value is not None]
    if not valid_values:
        return 0.0
    return max(0.0, min(100.0, sum(valid_values) / len(valid_values)))


def relative_similarity_score(true_value, sim_value) -> float:
    true_num = safe_float(true_value)
    sim_num = safe_float(sim_value)
    if true_num is None or sim_num is None:
        return 0.0
    baseline = max(abs(true_num), 1e-9)
    relative_gap = abs(sim_num - true_num) / baseline
    return max(0.0, min(100.0, 100.0 / (1.0 + relative_gap)))


def pct_diff_score(pct_value) -> float:
    pct_num = safe_float(pct_value)
    if pct_num is None:
        return 0.0
    return max(0.0, min(100.0, 100.0 / (1.0 + abs(pct_num) / 100.0)))


def zero_target_score(value) -> float:
    number = safe_float(value)
    if number is None:
        return 0.0
    return max(0.0, min(100.0, 100.0 / (1.0 + abs(number))))


def unit_interval_score(value) -> float:
    number = safe_float(value)
    if number is None:
        return 0.0
    return max(0.0, min(100.0, number * 100.0))
