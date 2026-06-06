from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs

from model.ABM.analytics.context import build_task_context
from model.ABM.analytics.crash_risk import build_crash_risk_payload
from model.ABM.analytics.investor_composition import build_investor_composition_payload
from model.ABM.analytics.io import read_json
from model.ABM.analytics.order_dynamics import build_order_dynamics_payload
from model.ABM.analytics.performance import build_performance_comparison_payload
from model.ABM.analytics.price_synthesis import build_price_synthesis_payload
from utils.function.func import get_project_root


class ABMV2AnalyticsService:
    def __init__(self) -> None:
        self.meta_root = Path(get_project_root()).resolve() / "meta"

    def get_analytics(self, sign: str, analysis_type: str) -> Dict[str, Any]:
        context = build_task_context(self.meta_root, sign)
        base_analysis_type, options = parse_analysis_request(analysis_type)
        payload = self._load_analysis_payload(context, base_analysis_type, options)
        if base_analysis_type in {
            "order_dynamics",
            "price_synthesis",
            "crash_risk",
            "investor_composition",
            "performance_comparison",
        }:
            return payload
        return {
            "sign": sign,
            "slot": 0,
            "stock_code": context.stock_code,
            "analysis_type": base_analysis_type,
            "task_root": str(context.task_dir),
            "payload": payload,
        }

    def _load_analysis_payload(self, context, analysis_type: str, options: Dict[str, str]) -> Dict[str, Any]:
        if analysis_type == "order_dynamics":
            params = read_json(context.runtime_params_path)
            return build_order_dynamics_payload(context.abm_root, params, options.get("date", ""))
        if analysis_type == "price_synthesis":
            return build_price_synthesis_payload(context.abm_root)
        if analysis_type == "crash_risk":
            return build_crash_risk_payload(context.predict_root)
        if analysis_type == "investor_composition":
            params = read_json(context.runtime_params_path)
            abm_params = params.get("abm", {}) if isinstance(params.get("abm"), dict) else {}
            structural_params = (
                abm_params.get("structural_params", {})
                if isinstance(abm_params.get("structural_params"), dict)
                else {}
            )
            return build_investor_composition_payload(structural_params, context.stock_code)
        if analysis_type == "performance_comparison":
            return build_performance_comparison_payload(context.abm_root, options.get("selectedModel", "ABM"))
        raise ValueError(f"unsupported analysisType: {analysis_type}")


def parse_analysis_request(raw_analysis_type: str) -> tuple:
    analysis_type = (raw_analysis_type or "").strip()
    if "?" not in analysis_type:
        return analysis_type, {}

    base, _, query = analysis_type.partition("?")
    parsed = parse_qs(query, keep_blank_values=False)
    options = {key: values[-1] for key, values in parsed.items() if values}
    return base.strip(), options
