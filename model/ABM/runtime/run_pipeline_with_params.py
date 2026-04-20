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


def _run(cmd: list[str], env: dict[str, str], title: str) -> None:
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

    predict_enabled = bool(predict_cfg.get("enabled", True))
    if predict_enabled:
        predict_method = str(predict_cfg.get("method", "auto"))
        predict_horizon = int(predict_cfg.get("horizon", 22))
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
        if predict_method == "abm_fv" and "fv_next" in predict_cfg:
            predict_cmd.extend(["--fv_next", str(predict_cfg["fv_next"])])
        _run(predict_cmd, env, "Predict No-FV")
    else:
        stage_log("Predict No-FV skipped")

    _run([sys.executable, str(BASE_DIR / "test.py"), str(input_csv)], env, "ABM Calibration + Simulation")

    code = str(eval_cfg.get("code", input_csv.stem))
    market = str(eval_cfg.get("market", "SM"))
    generate_models = bool(eval_cfg.get("generate_models", True))
    gan_epochs = int(eval_cfg.get("gan_epochs", 50))
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
        "--gan-epochs",
        str(gan_epochs),
    ]
    eval_cmd.append("--generate-models" if generate_models else "--no-generate-models")
    _run(eval_cmd, env, "ABM/GBM/GAN Evaluation")

    stage_log("pipeline finished")
    print("\nPipeline finished.", flush=True)


if __name__ == "__main__":
    main()
