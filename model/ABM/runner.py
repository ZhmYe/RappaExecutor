import json
import mimetypes
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from logger.logger import logWriter as log
from model.ABM.stock_data_provider import configured_data_source_mode, materialize_remote_stock_csv
from utils.function.func import get_project_root


ABM_PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_ABM_V2_RUNTIME_ROOT = ABM_PACKAGE_ROOT / "runtime"
PROJECT1_ABM_ROOT = Path(
    os.environ.get("RAPPA_ABM_V2_PROJECT_ROOT", str(DEFAULT_ABM_V2_RUNTIME_ROOT))
).resolve()

DEFAULT_ABM_STOCK_DATA_DIR = "/root/rappa/stockdata"


def normalize_code(code: str) -> str:
    code = str(code).strip()
    if code.isdigit():
        return code.zfill(6) if len(code) < 6 else code
    return code


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def guess_content_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    if guessed:
        return guessed
    if path.suffix.lower() == ".json":
        return "application/json"
    if path.suffix.lower() in {".csv", ".log", ".txt"}:
        return "text/plain"
    return "application/octet-stream"


def executor_config_value(*keys: str) -> str:
    config_path = Path(get_project_root()).resolve() / "config.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception:
        return ""
    if not isinstance(config, dict):
        return ""

    for key in keys:
        value = config.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def configured_stock_data_dir() -> Path:
    value = os.getenv("ABM_STOCK_DATA_DIR", "").strip()
    if not value:
        value = executor_config_value("ABMStockDataDir", "ABM_STOCK_DATA_DIR")
    if not value:
        value = DEFAULT_ABM_STOCK_DATA_DIR
    return Path(value).resolve()


def configured_stock_param_dir(stock_data_dir: Path) -> Path:
    value = os.getenv("ABM_STOCK_PARAM_DIR", "").strip()
    if not value:
        value = executor_config_value("ABMStockParamDir", "ABM_STOCK_PARAM_DIR")
    if not value:
        value = str(stock_data_dir / "params")
    return Path(value).resolve()


class ABMV2PipelineRunner:
    def __init__(self) -> None:
        self.executor_root = Path(get_project_root()).resolve()
        self.meta_root = self.executor_root / "meta"
        self.meta_root.mkdir(parents=True, exist_ok=True)
        self.local_data_root = Path(__file__).resolve().parent / "data"
        shared_data_root = configured_stock_data_dir()
        self.data_roots = self._build_data_roots(shared_data_root, self.local_data_root)
        self.data_root = self.data_roots[0]
        self.local_model_params_root = Path(__file__).resolve().parent / "offline_params"
        shared_model_params_root = configured_stock_param_dir(shared_data_root)
        self.model_params_roots = self._build_data_roots(shared_model_params_root, self.local_model_params_root)
        self.model_params_root = self.model_params_roots[0]
        self.runtime_root = PROJECT1_ABM_ROOT
        self.template_path = PROJECT1_ABM_ROOT / "params_quickstart.json"
        self.pipeline_path = PROJECT1_ABM_ROOT / "run_pipeline_with_params.py"
        self.converter_path = PROJECT1_ABM_ROOT / "preprocess" / "auto_convert_l2_to_abm.py"
        if not self.template_path.exists() or not self.pipeline_path.exists():
            raise FileNotFoundError(
                "ABM_V2 runtime files missing under "
                f"{self.runtime_root}; expected {self.template_path.name} and {self.pipeline_path.name}"
            )

    def _build_data_roots(self, *roots: Path) -> List[Path]:
        data_roots: List[Path] = []
        for root in roots:
            resolved = root.resolve()
            if resolved not in data_roots:
                data_roots.append(resolved)
        return data_roots

    def run(self, params: Dict[str, Any], output_size: int = 1) -> pd.DataFrame:
        params = dict(params or {})
        task_hash = str(params.pop("__slot_hash", "")).strip() or f"ABM_V2_{int(time.time() * 1000)}"
        params.pop("__slot_size", None)
        task_sign = str(params.pop("__slot_sign", "")).strip()
        task_label = task_sign or task_hash
        task_dir = self._resolve_task_dir(task_sign, task_hash)
        if task_dir.exists():
            shutil.rmtree(task_dir)
        input_dir = task_dir / "input"
        runtime_dir = task_dir / "runtime_params"
        output_dir = task_dir / "outputs"
        log_dir = task_dir / "logs"
        for path in (input_dir, runtime_dir, output_dir, log_dir):
            path.mkdir(parents=True, exist_ok=True)

        input_hint = str(params.get("input_csv", "")).strip()
        raw_code = str(
            params.get("evaluation", {}).get("code")
            if isinstance(params.get("evaluation"), dict)
            else ""
        ).strip()
        if not raw_code:
            raw_code = str(params.get("stockCode") or params.get("dataset") or Path(input_hint).stem)
        eval_code = normalize_code(raw_code)
        runtime_input, stock_root = self._resolve_runtime_input(params, input_dir, eval_code, task_label)

        task_info = {
            "task_hash": task_hash,
            "sign": task_sign,
            "slot": 0,
            "raw_code": raw_code or eval_code,
            "normalized_code": eval_code,
            "input_csv": str(runtime_input),
            "stock_root": str(stock_root),
            "created_at": int(time.time()),
        }
        with open(task_dir / "task_info.json", "w", encoding="utf-8") as f:
            json.dump(task_info, f, ensure_ascii=False, indent=2)

        pipeline_params = self._build_pipeline_params(runtime_input, stock_root, output_dir, params, eval_code)
        params_path = runtime_dir / "params.json"
        with open(params_path, "w", encoding="utf-8") as f:
            json.dump(pipeline_params, f, ensure_ascii=False, indent=2)
        log.write_log("EXECUTION", f"ABM_V2 {task_label}: runtime params written to {params_path}")

        stdout_path = log_dir / "pipeline.stdout.log"
        stderr_path = log_dir / "pipeline.stderr.log"
        self._run_pipeline(params_path, stdout_path, stderr_path, task_label)

        manifest = self._collect_manifest(task_hash, task_sign, raw_code or eval_code, eval_code, task_dir)
        if manifest.empty:
            raise RuntimeError(f"ABM_V2 task {task_hash} produced no artifacts under {task_dir}")
        log.write_log("EXECUTION", f"ABM_V2 {task_label}: artifact collection complete, total={len(manifest)}")
        return manifest

    def _resolve_task_dir(self, task_sign: str, task_hash: str) -> Path:
        if task_sign:
            return self.meta_root / task_sign / "0"
        return self.meta_root / task_hash

    def _resolve_runtime_input(
        self,
        params: Dict[str, Any],
        input_dir: Path,
        eval_code: str,
        task_label: str,
    ) -> tuple[Path, Path]:
        mode = configured_data_source_mode()
        local_error: Optional[Exception] = None
        if mode in {"local", "auto"}:
            try:
                input_csv = self._resolve_input_csv(params)
                return self._prepare_runtime_input(input_csv, input_dir, eval_code, task_label)
            except FileNotFoundError as exc:
                local_error = exc
                if mode == "local":
                    raise

        if mode in {"dolphindb", "auto"}:
            local_input = input_dir / f"{eval_code}.csv"
            log.write_log("EXECUTION", f"ABM_V2 {task_label}: materialize task-local input from dolphindb")
            try:
                runtime_input = materialize_remote_stock_csv(params, local_input)
            except Exception as exc:
                if local_error is not None:
                    raise RuntimeError(f"{local_error}; dolphindb fallback failed: {exc}") from exc
                raise
            return runtime_input.resolve(), runtime_input.parent.resolve()

        raise ValueError(f"Unsupported ABMStockDataSource: {mode}")

    def _resolve_input_csv(self, params: Dict[str, Any]) -> Path:
        input_csv = str(params.get("input_csv", "")).strip()
        checked: List[str] = []

        for raw_name in self._candidate_input_names(params, input_csv):
            for data_root in self.data_roots:
                local_path = (data_root / raw_name).resolve()
                checked.append(str(local_path))
                if local_path.exists():
                    return local_path

        for code in self._candidate_stock_codes(params, input_csv):
            for candidate in self._candidate_csv_paths(code):
                checked.append(str(candidate))
                if candidate.exists():
                    return candidate.resolve()

        raise FileNotFoundError(
            "ABM_V2 input csv not found in ABM data directories; checked: "
            + ", ".join(dict.fromkeys(checked))
        )

    def _candidate_input_names(self, params: Dict[str, Any], input_csv: str) -> List[str]:
        names: List[str] = []
        if input_csv:
            logical_name = Path(input_csv).name.strip()
            if logical_name and logical_name not in names:
                names.append(logical_name)

        for code in self._candidate_stock_codes(params, input_csv):
            csv_name = f"{normalize_code(code)}.csv"
            if csv_name not in names:
                names.append(csv_name)
        return names

    def _candidate_stock_codes(self, params: Dict[str, Any], input_csv: str) -> List[str]:
        codes: List[str] = []
        for raw in (
            params.get("stockCode"),
            params.get("evaluation", {}).get("code") if isinstance(params.get("evaluation"), dict) else None,
            params.get("dataset"),
            Path(input_csv).stem if input_csv else None,
        ):
            text = normalize_code(str(raw).strip()) if raw not in (None, "") else ""
            if text and text not in codes:
                codes.append(text)
        return codes

    def _candidate_csv_paths(self, code: str) -> List[Path]:
        code = normalize_code(code)
        candidates: List[Path] = []
        for data_root in self.data_roots:
            exact = data_root / f"{code}.csv"
            candidates.append(exact)

            pattern_matches = sorted(data_root.glob(f"*_{code}_*.csv"))
            if not pattern_matches:
                pattern_matches = sorted(data_root.glob(f"*{code}*.csv"))
            candidates.extend(pattern_matches)
        return candidates

    def _prepare_runtime_input(
        self,
        source_path: Path,
        input_dir: Path,
        eval_code: str,
        task_label: str,
    ) -> tuple:
        local_input = input_dir / f"{eval_code}.csv"
        if self._can_reuse_input_csv(source_path, eval_code):
            log.write_log("EXECUTION", f"ABM_V2 {task_label}: reuse local input {source_path}")
            return source_path.resolve(), source_path.parent.resolve()

        log.write_log("EXECUTION", f"ABM_V2 {task_label}: materialize task-local input from {source_path}")
        self._materialize_input_csv(source_path, local_input)
        return local_input.resolve(), local_input.parent.resolve()

    def _can_reuse_input_csv(self, source_path: Path, eval_code: str) -> bool:
        if not self._is_standard_abm_csv(source_path):
            return False
        if source_path.name == f"{eval_code}.csv":
            return True
        return (source_path.parent / f"{eval_code}.csv").exists()

    def _materialize_input_csv(self, source_path: Path, local_input: Path) -> None:
        if self._is_standard_abm_csv(source_path):
            shutil.copyfile(source_path, local_input)
            return
        self._convert_raw_input_csv(source_path, local_input)

    def _is_standard_abm_csv(self, path: Path) -> bool:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                header = [item.strip() for item in f.readline().strip().split(",")]
        except OSError:
            return False
        return "close" in header and ("Time" in header or "date" in header)

    def _convert_raw_input_csv(self, source_path: Path, local_input: Path) -> None:
        if not self.converter_path.exists():
            raise FileNotFoundError(f"ABM raw converter not found: {self.converter_path}")

        local_input.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable,
            str(self.converter_path),
            "--inputs",
            str(source_path),
            "--output-dir",
            str(local_input.parent),
        ]
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT1_ABM_ROOT),
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "PYTHONNOUSERSITE": "1"},
        )
        if proc.returncode != 0:
            raise RuntimeError(
                "ABM_V2 raw input conversion failed for "
                f"{source_path}; stdout={proc.stdout[-400:]}, stderr={proc.stderr[-400:]}"
            )
        if not local_input.exists():
            raise FileNotFoundError(f"ABM_V2 converted csv missing: {local_input}")

    def _build_pipeline_params(
        self,
        runtime_input: Path,
        stock_root: Path,
        output_dir: Path,
        params: Dict[str, Any],
        eval_code: str,
    ) -> Dict[str, Any]:
        if not self.template_path.exists():
            raise FileNotFoundError(f"ABM_V2 template params missing: {self.template_path}")
        with open(self.template_path, "r", encoding="utf-8") as f:
            template = json.load(f)

        user_cfg = {k: v for k, v in params.items() if not str(k).startswith("__")}
        pipeline_params = deep_merge(template, user_cfg)
        pipeline_params["input_csv"] = str(runtime_input)

        runtime_cfg = dict(pipeline_params.get("runtime", {}) or {})
        runtime_cfg["output_root"] = str(output_dir)
        pipeline_params["runtime"] = runtime_cfg

        eval_cfg = dict(pipeline_params.get("evaluation", {}) or {})
        user_eval_cfg = dict(params.get("evaluation", {}) or {})
        eval_cfg["code"] = str(user_eval_cfg.get("code", eval_code) or eval_code)
        eval_cfg["stock_root"] = str(stock_root)
        pipeline_params["evaluation"] = eval_cfg

        abm_cfg = dict(pipeline_params.get("abm", {}) or {})
        if not str(abm_cfg.get("mode", "")).strip():
            abm_cfg["mode"] = "auto"
        abm_cfg["model_params_root"] = str(self.model_params_root.resolve())
        abm_cfg["model_params_json"] = self._resolve_local_model_params_json(
            abm_cfg.get("model_params_json"),
            eval_cfg["code"],
        )
        pipeline_params["abm"] = abm_cfg

        return pipeline_params

    def _resolve_local_model_params_json(self, raw_path: Any, code: str) -> str:
        raw_text = str(raw_path or "").strip()
        if raw_text:
            candidate = Path(raw_text)
            if not candidate.is_absolute():
                candidate = (PROJECT1_ABM_ROOT / candidate).resolve()
            if candidate.exists() and self._is_under(candidate, self.executor_root):
                return str(candidate)

        for model_params_root in self.model_params_roots:
            for candidate_code in self._candidate_model_param_codes(code):
                candidate = model_params_root / candidate_code / "model_params.json"
                if candidate.exists():
                    return str(candidate.resolve())
        return ""

    def _candidate_model_param_codes(self, code: str) -> List[str]:
        normalized = normalize_code(code)
        candidates = [normalized]
        if normalized.isdigit():
            stripped = str(int(normalized))
            if stripped not in candidates:
                candidates.append(stripped)
        return candidates

    def _is_under(self, path: Path, parent: Path) -> bool:
        try:
            path.resolve().relative_to(parent.resolve())
            return True
        except ValueError:
            return False

    def _run_pipeline(self, params_path: Path, stdout_path: Path, stderr_path: Path, task_label: str) -> None:
        cmd = [sys.executable, str(self.pipeline_path), "--params", str(params_path)]
        env = {**os.environ, "PYTHONNOUSERSITE": "1", "PYTHONUNBUFFERED": "1"}
        log.write_log("EXECUTION", f"ABM_V2 {task_label}: pipeline start")

        with open(stdout_path, "w", encoding="utf-8") as stdout_file, open(stderr_path, "w", encoding="utf-8") as stderr_file:
            proc = subprocess.Popen(
                cmd,
                cwd=str(PROJECT1_ABM_ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                env=env,
            )

            stdout_thread = threading.Thread(
                target=self._stream_pipe,
                args=(proc.stdout, stdout_file, task_label, True),
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=self._stream_pipe,
                args=(proc.stderr, stderr_file, task_label, False),
                daemon=True,
            )
            stdout_thread.start()
            stderr_thread.start()

            return_code = proc.wait()
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)

        log.write_log("EXECUTION", f"ABM_V2 {task_label}: pipeline finish")
        if return_code != 0:
            raise RuntimeError(
                f"ABM_V2 pipeline failed with code {return_code}; "
                f"see {stdout_path} and {stderr_path}"
            )

    def _stream_pipe(self, pipe, sink, task_label: str, mirror_stage_log: bool) -> None:
        if pipe is None:
            return
        try:
            for line in pipe:
                sink.write(line)
                sink.flush()
                clean = line.strip()
                if mirror_stage_log and clean.startswith("[ABM_V2]"):
                    log.write_log("EXECUTION", f"ABM_V2 {task_label}: {clean}")
        finally:
            pipe.close()

    def _collect_manifest(
        self,
        task_hash: str,
        task_sign: str,
        raw_code: str,
        normalized_code: str,
        task_dir: Path,
    ) -> pd.DataFrame:
        files = self._iter_text_artifacts(task_dir)
        rows: List[Dict[str, Any]] = []
        for path in files:
            rel = path.relative_to(task_dir).as_posix()
            rows.append(
                {
                    "task_hash": task_hash,
                    "sign": task_sign,
                    "slot": 0,
                    "raw_code": raw_code,
                    "code": normalized_code,
                    "artifact_name": path.name,
                    "relative_path": rel,
                    "content_type": guess_content_type(path),
                    "size_bytes": path.stat().st_size,
                    "content": path.read_text(encoding="utf-8", errors="replace"),
                }
            )
        return pd.DataFrame(rows)

    def _iter_text_artifacts(self, task_dir: Path) -> Iterable[Path]:
        if not task_dir.exists():
            return []
        allowed_suffixes = {".csv", ".json", ".log", ".txt"}
        return sorted(
            p for p in task_dir.rglob("*")
            if p.is_file()
            and p.suffix.lower() in allowed_suffixes
            and "input" not in p.relative_to(task_dir).parts
        )
