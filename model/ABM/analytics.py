import csv
import json
from pathlib import Path
from typing import Any, Dict

from utils.function.func import get_project_root


class ABMV2AnalyticsService:
    def __init__(self) -> None:
        self.meta_root = Path(get_project_root()).resolve() / "meta"

    def get_analytics(self, sign: str, analysis_type: str) -> Dict[str, Any]:
        task_dir = self._resolve_task_dir(sign)
        task_info = self._read_json(task_dir / "task_info.json")
        stock_code = str(
            task_info.get("normalized_code")
            or task_info.get("raw_code")
            or sign.rsplit("-", 1)[-1]
        )
        payload = self._load_analysis_payload(task_dir, stock_code, analysis_type)
        return {
            "sign": sign,
            "slot": 0,
            "stock_code": stock_code,
            "analysis_type": analysis_type,
            "task_root": str(task_dir),
            "payload": payload,
        }

    def _resolve_task_dir(self, sign: str) -> Path:
        task_dir = self.meta_root / sign / "0"
        if not task_dir.exists():
            raise FileNotFoundError(f"task directory not found: {task_dir}")
        return task_dir

    def _load_analysis_payload(self, task_dir: Path, stock_code: str, analysis_type: str) -> Dict[str, Any]:
        abm_root = task_dir / "outputs" / "abm" / stock_code
        predict_root = task_dir / "outputs" / "predict"

        if analysis_type == "order_dynamics":
            return {
                "order_behavior": self._read_csv(abm_root / "order_behavior.csv"),
                "order_book_reuse": self._read_csv(abm_root / "order_book_reuse.csv"),
            }
        if analysis_type == "price_synthesis":
            payload = {
                "kline_ohlcv": self._read_csv(abm_root / "kline_ohlcv.csv"),
                "mid_price": self._read_csv(abm_root / "mid_price.csv"),
            }
            multiple_market = abm_root / "multiple_market.csv"
            if multiple_market.exists():
                payload["multiple_market"] = self._read_csv(multiple_market)
            return payload
        if analysis_type == "crash_risk":
            return {
                "predict_fv": self._read_csv(predict_root / "predict_fv.csv"),
                "predict_meta": self._read_json(predict_root / "predict_fv_meta.json"),
            }
        if analysis_type == "investor_composition":
            params = self._read_json(task_dir / "runtime_params" / "params.json")
            abm_params = params.get("abm", {}) if isinstance(params.get("abm"), dict) else {}
            return {
                "structural_params": abm_params.get("structural_params", {}),
                "runtime_params": abm_params,
            }
        if analysis_type == "performance_comparison":
            return {
                "all_metrics": self._read_csv(abm_root / "cal_all_compare_metrics.csv"),
                "diff_metrics": self._read_csv(abm_root / "cal_compare_diff_metrics.csv"),
                "level_metrics": self._read_csv(abm_root / "cal_compare_level_metrics.csv"),
            }
        raise ValueError(f"unsupported analysisType: {analysis_type}")

    def _read_csv(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"analysis file not found: {path}")
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            columns = list(reader.fieldnames or [])
        return {
            "path": str(path),
            "columns": columns,
            "rows": rows,
        }

    def _read_json(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"analysis file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
