#!/usr/bin/env python3
"""
Parameter-file driven pipeline for frontend/backend integration.

Usage:
  python run_pipeline_with_params.py --params params.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def stage_log(message: str) -> None:
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[ABM_V2] {now} {message}", flush=True)


def _run(cmd: list, env: dict, title: str) -> None:
    print(f"\n{'=' * 72}\n[{title}]", flush=True)
    print(" ".join(cmd), flush=True)
    start_time = time.time()
    result = subprocess.run(cmd, cwd=str(BASE_DIR), env=env, check=False)
    elapsed = time.time() - start_time
    if result.returncode != 0:
        stage_log(f"{title} failed, code={result.returncode}, elapsed={elapsed:.1f}s")
        raise RuntimeError(f"Step failed: {title}, return code={result.returncode}")
    stage_log(f"{title} completed, elapsed={elapsed:.1f}s")


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("params file root must be a JSON object")
    return data


def _candidate_codes(raw_code: str) -> list:
    code = str(raw_code).strip()
    if not code:
        return []
    candidates = [code]
    if code.isdigit():
        candidates.append(code.zfill(6))
        candidates.append(str(int(code)))
    seen = set()
    result = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            result.append(candidate)
    return result


def _resolve_model_params_path(abm_cfg: dict, code: str, input_csv: Path) -> Path | None:
    explicit = str(abm_cfg.get("model_params_json", "")).strip()
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = (BASE_DIR / path).resolve()
        return path

    root = str(abm_cfg.get("model_params_root", "")).strip()
    if not root:
        return None
    root_path = Path(root)
    if not root_path.is_absolute():
        root_path = (BASE_DIR / root_path).resolve()

    for candidate_code in _candidate_codes(code) + _candidate_codes(input_csv.stem):
        path = root_path / candidate_code / "model_params.json"
        if path.exists():
            return path
    return root_path / str(code) / "model_params.json"


def _resolve_abm_mode(abm_cfg: dict) -> str:
    mode = str(abm_cfg.get("mode", "auto")).strip().lower()
    if mode not in {"auto", "precalibrated", "calibrate"}:
        raise ValueError(f"Invalid abm.mode={mode}, expected one of: auto|precalibrated|calibrate")
    return mode


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ABM pipeline with JSON params")
    parser.add_argument("--params", required=True, help="Path to params JSON file")
    args = parser.parse_args()

    params_path = Path(args.params).resolve()
    cfg = _load_json(params_path)
    stage_log(f"pipeline params loaded: {params_path}")

    input_csv = (BASE_DIR / cfg.get("input_csv", "600000.csv")).resolve()
    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")
    stage_log(f"input csv resolved: {input_csv}")

    predict_cfg = cfg.get("predict", {}) or {}
    abm_cfg = cfg.get("abm", {}) or {}
    eval_cfg = cfg.get("evaluation", {}) or {}
    runtime_cfg = cfg.get("runtime", {}) or {}

    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"
    env["ABM_SKIP_STRUCT_PROMPT"] = "1"
    env["INPUT_CSV"] = str(input_csv)
    env["EPOCH"] = str(abm_cfg.get("epochs", 100))

    output_root_raw = runtime_cfg.get("output_root", "")
    output_root = Path(output_root_raw).resolve() if output_root_raw else None
    if output_root is not None:
        output_root.mkdir(parents=True, exist_ok=True)
        predict_dir = output_root / "predict"
        abm_output_root = output_root / "abm"
        model_root_default = output_root / "model_result"
        predict_dir.mkdir(parents=True, exist_ok=True)
        abm_output_root.mkdir(parents=True, exist_ok=True)
        model_root_default.mkdir(parents=True, exist_ok=True)
        env["ABM_OUTPUT_ROOT"] = str(abm_output_root)
        stage_log(f"runtime output root ready: {output_root}")
    else:
        predict_dir = None
        abm_output_root = None
        model_root_default = None

    if "max_rows" in abm_cfg:
        env["MAX_ROWS"] = str(abm_cfg["max_rows"])
    if "learning_rate" in abm_cfg:
        env["LEARNING_RATE"] = str(abm_cfg["learning_rate"])
    if "epsilon" in abm_cfg:
        env["EPSILON"] = str(abm_cfg["epsilon"])
    if "seed_count" in abm_cfg:
        env["SEED_COUNT"] = str(abm_cfg["seed_count"])
    if "bootstrap_samples" in abm_cfg:
        env["BOOTSTRAP_SAMPLES"] = str(abm_cfg["bootstrap_samples"])
    if "patience" in abm_cfg:
        env["PATIENCE"] = str(abm_cfg["patience"])

    structural_params = abm_cfg.get("structural_params", {}) or {}
    env["ABM_STRUCT_PARAMS_JSON"] = json.dumps(structural_params, ensure_ascii=False)
    stage_log(f"structural params ready: {sorted(structural_params.keys())}")

    code = str(eval_cfg.get("code", input_csv.stem))
    abm_mode = _resolve_abm_mode(abm_cfg)
    model_params_path = _resolve_model_params_path(abm_cfg, code, input_csv)
    if abm_mode == "calibrate":
        use_precalibrated = False
    elif abm_mode == "precalibrated":
        if model_params_path is None or not model_params_path.exists():
            raise FileNotFoundError(
                f"abm.mode=precalibrated but model params not found: {model_params_path}"
            )
        use_precalibrated = True
    else:
        use_precalibrated = bool(model_params_path is not None and model_params_path.exists())

    if use_precalibrated and model_params_path is not None:
        env["ABM_MODEL_PARAMS_FILE"] = str(model_params_path)
        stage_log(f"ABM mode=precalibrated, using params: {model_params_path}")
    else:
        stage_log("ABM mode=calibrate (online)")

    predict_enabled = bool(predict_cfg.get("enabled", True))
    if predict_enabled:
        predict_method = str(predict_cfg.get("method", "kalman_rw"))
        predict_horizon = int(predict_cfg.get("horizon", 1))
        predict_cmd = [
            sys.executable,
            str(BASE_DIR / "predict_no_fv" / "predict_no_fv.py"),
            "--input_mode",
            "manual",
            "--input_csv",
            str(input_csv),
            "--method",
            predict_method,
            "--horizon",
            str(predict_horizon),
            "--tune",
            "auto",
        ]
        if predict_dir is not None:
            predict_cmd.extend(
                [
                    "--output_csv",
                    str(predict_dir / "predict_fv.csv"),
                    "--meta_json",
                    str(predict_dir / "predict_fv_meta.json"),
                ]
            )
        if "risk_drop_levels" in predict_cfg:
            levels = predict_cfg.get("risk_drop_levels", [0.05])
            if isinstance(levels, (list, tuple)):
                levels_arg = ",".join(str(item) for item in levels)
            else:
                levels_arg = str(levels)
            predict_cmd.extend(["--risk_drop_levels", levels_arg])
        if predict_method == "abm_fv":
            abm_fv_cfg = predict_cfg.get("abm_fv_options", {}) or {}
            fv_file = str(predict_cfg.get("fv_file", abm_fv_cfg.get("fv_file", ""))).strip()
            if not fv_file:
                raise ValueError("predict.method=abm_fv requires predict.fv_file")
            fv_file_path = Path(fv_file)
            if not fv_file_path.is_absolute():
                fv_file_path = (BASE_DIR / fv_file_path).resolve()
            predict_cmd.extend(["--fv_file", str(fv_file_path)])
            predict_cmd.extend(["--lookback_days", str(int(predict_cfg.get("lookback_days", abm_fv_cfg.get("lookback_days", 7))))])
            predict_cmd.extend(["--abm_rounds", str(int(predict_cfg.get("abm_rounds", abm_fv_cfg.get("abm_rounds", 100))))])
            intraday_steps = predict_cfg.get("intraday_steps", abm_fv_cfg.get("intraday_steps"))
            if intraday_steps is not None:
                predict_cmd.extend(["--intraday_steps", str(int(intraday_steps))])
            mp = str(predict_cfg.get("model_params_json", "")).strip()
            if not mp and model_params_path is not None and model_params_path.exists():
                mp = str(model_params_path)
            if mp:
                mp_path = Path(mp)
                if not mp_path.is_absolute():
                    mp_path = (BASE_DIR / mp_path).resolve()
                predict_cmd.extend(["--model_params_json", str(mp_path)])
        _run(predict_cmd, env, "Predict No-FV")
    else:
        stage_log("Predict No-FV skipped")

    abm_title = "ABM Simulation (Load Params)" if use_precalibrated else "ABM Calibration + Simulation"
    _run([sys.executable, str(BASE_DIR / "test.py"), str(input_csv)], env, abm_title)

    market = str(eval_cfg.get("market", "SM"))
    generate_models = bool(eval_cfg.get("generate_models", True))
    vrnn_epochs = int(eval_cfg.get("vrnn_epochs", 50))
    timegan_epochs = int(eval_cfg.get("timegan_epochs", 50))
    min_deep_samples = int(eval_cfg.get("min_deep_samples", 200))
    allow_fallback = bool(eval_cfg.get("allow_fallback", True))
    if abm_output_root is not None:
        abm_root_cfg = str(eval_cfg.get("abm_root", "") or "").strip()
        model_root_cfg = str(eval_cfg.get("model_root", "") or "").strip()
        stock_root_cfg = str(eval_cfg.get("stock_root", "") or "").strip()

        abm_root = Path(abm_root_cfg).resolve() if abm_root_cfg and Path(abm_root_cfg).is_absolute() else abm_output_root
        stock_root = Path(stock_root_cfg).resolve() if stock_root_cfg else Path(input_csv.parent).resolve()
        model_root = Path(model_root_cfg).resolve() if model_root_cfg and Path(model_root_cfg).is_absolute() else model_root_default
    else:
        abm_root = Path(eval_cfg.get("abm_root", "simulated_result")).resolve()
        stock_root = Path(eval_cfg.get("stock_root", f"{market}_stock")).resolve()
        model_root = Path(eval_cfg.get("model_root", f"{market}_result")).resolve()

    abm_root.mkdir(parents=True, exist_ok=True)
    model_root.mkdir(parents=True, exist_ok=True)

    eval_cmd = [
        sys.executable,
        str(BASE_DIR / "calculate.py"),
        "--market",
        market,
        "--code",
        code,
        "--abm-root",
        str(abm_root),
        "--stock-root",
        str(stock_root),
        "--model-root",
        str(model_root),
        "--vrnn-epochs",
        str(vrnn_epochs),
        "--timegan-epochs",
        str(timegan_epochs),
        "--min-deep-samples",
        str(min_deep_samples),
    ]
    if not allow_fallback:
        eval_cmd.append("--no-fallback")
    eval_cmd.append("--generate-models" if generate_models else "--no-generate-models")
    _run(eval_cmd, env, "ABM/VRNN/TimeGAN Evaluation")

    stage_log("pipeline finished")
    print("\nPipeline finished.", flush=True)


if __name__ == "__main__":
    main()
