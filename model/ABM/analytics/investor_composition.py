from typing import Any, Dict, Iterable, List, Tuple


TRADER_TYPE_DEFINITIONS: List[Tuple[str, str, str]] = [
    ("fund", "基本面", "N_FT"),
    ("longMom", "长动量", "N_LMT"),
    ("shortMom", "短动量", "N_SMT"),
    ("noise", "噪声", "N_NT"),
]


def build_investor_composition_payload(
    structural_params: Dict[str, Any],
    stock_code: str,
) -> Dict[str, Any]:
    values = []
    pie = []
    history_series: Dict[str, List[int]] = {}
    raw_params: Dict[str, int] = {}

    for series_key, label, param_key in TRADER_TYPE_DEFINITIONS:
        value = safe_int(structural_params.get(param_key), 0)
        values.append(value)
        pie.append({"value": value, "name": label})
        history_series[series_key] = [value]
        raw_params[param_key] = value

    total = sum(values)
    composition = []
    for index, (series_key, label, param_key) in enumerate(TRADER_TYPE_DEFINITIONS):
        value = values[index]
        ratio = round(value / total, 6) if total > 0 else 0.0
        composition.append(
            {
                "key": series_key,
                "name": label,
                "param": param_key,
                "value": value,
                "ratio": ratio,
            }
        )

    return {
        "yearData": {
            "bar": values,
            "pie": pie,
        },
        "historyData": {
            "categories": ["当前配置"],
            "fund": history_series["fund"],
            "longMom": history_series["longMom"],
            "shortMom": history_series["shortMom"],
            "noise": history_series["noise"],
        },
        "meta": {
            "stockCode": stock_code,
            "total": total,
            "source": "abm.structural_params",
            "composition": composition,
            "rawParams": raw_params,
        },
    }


def safe_int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default
