from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from model.ABM.analytics.io import read_json


@dataclass
class TaskAnalyticsContext:
    sign: str
    task_dir: Path
    stock_code: str
    abm_root: Path
    predict_root: Path
    runtime_params_path: Path


def resolve_stock_code(task_info: Dict, sign: str) -> str:
    return str(
        task_info.get("raw_code")
        or sign.rsplit("-", 1)[-1]
        or task_info.get("normalized_code")
        or sign.rsplit("-", 1)[-1]
    )


def _unique_candidates(values: Iterable[str]) -> List[str]:
    ordered: List[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in ordered:
            ordered.append(text)
    return ordered


def _trim_leading_zeros(code: str) -> str:
    text = str(code).strip()
    if not text or not text.isdigit():
        return text
    return text.lstrip("0") or "0"


def resolve_abm_root(task_dir: Path, task_info: Dict, stock_code: str) -> Path:
    abm_base = task_dir / "outputs" / "abm"
    normalized_code = str(task_info.get("normalized_code") or "").strip()
    candidates = _unique_candidates(
        [
            stock_code,
            normalized_code,
            _trim_leading_zeros(stock_code),
            _trim_leading_zeros(normalized_code),
        ]
    )

    for candidate in candidates:
        candidate_path = abm_base / candidate
        if candidate_path.exists():
            return candidate_path

    return abm_base / (normalized_code or stock_code)


def build_task_context(meta_root: Path, sign: str) -> TaskAnalyticsContext:
    task_dir = meta_root / sign / "0"
    if not task_dir.exists():
        raise FileNotFoundError(f"task directory not found: {task_dir}")
    task_info = read_json(task_dir / "task_info.json")
    stock_code = resolve_stock_code(task_info, sign)
    return TaskAnalyticsContext(
        sign=sign,
        task_dir=task_dir,
        stock_code=stock_code,
        abm_root=resolve_abm_root(task_dir, task_info, stock_code),
        predict_root=task_dir / "outputs" / "predict",
        runtime_params_path=task_dir / "runtime_params" / "params.json",
    )
