#!/usr/bin/env python3
"""
Stage B: merge converted 1min csv files by stock code.

Supports both:
1) Single month input (one folder)
2) Multi-month input (multiple folders/files)

Example:
  python stage_b_merge_by_code.py \
    --inputs d:\\Desktop\\stock\\data_defreq\\converted_examples \
    --output-dir d:\\Desktop\\stock\\data_defreq\\yearly_stock
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Merge converted csv files by stock code")
    p.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help="Input csv files or directories (single month or multi-month)",
    )
    p.add_argument("--output-dir", required=True, help="Merged output directory")
    p.add_argument(
        "--date-col",
        default="date",
        help="Date column name in converted csv (default: date)",
    )
    p.add_argument(
        "--dedup-keys",
        nargs="+",
        default=["stockid", "date"],
        help="Deduplication keys (default: stockid date)",
    )
    return p.parse_args()


def collect_csv_files(input_paths: List[str]) -> List[Path]:
    files: List[Path] = []
    for raw in input_paths:
        p = Path(raw).resolve()
        if p.is_file() and p.suffix.lower() == ".csv":
            files.append(p)
        elif p.is_dir():
            files.extend(sorted(p.glob("*.csv")))
    # de-duplicate while preserving order
    seen = set()
    unique_files = []
    for f in files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)
    return unique_files


def infer_code_from_filename(path: Path) -> str | None:
    m = re.search(r"(\d{6})", path.stem)
    return m.group(1) if m else None


def infer_code_from_data(df: pd.DataFrame) -> str | None:
    if "stockid" not in df.columns:
        return None
    vals = df["stockid"].dropna().astype(str).str.zfill(6).unique()
    if len(vals) == 1:
        return vals[0]
    return None


def load_and_tag(path: Path, date_col: str) -> Tuple[str, pd.DataFrame]:
    df = pd.read_csv(path)
    if date_col not in df.columns:
        raise ValueError(f"{path.name}: missing required date column `{date_col}`")

    # Parse date for sorting/validation
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).copy()

    code = infer_code_from_filename(path) or infer_code_from_data(df)
    if not code:
        raise ValueError(f"{path.name}: cannot infer stock code from filename or stockid")
    return code, df


def ensure_dedup_keys(df: pd.DataFrame, dedup_keys: List[str]) -> List[str]:
    keys = [k for k in dedup_keys if k in df.columns]
    if not keys:
        # fallback to date only
        keys = ["date"] if "date" in df.columns else [df.columns[0]]
    return keys


def merge_by_code(
    files: List[Path],
    output_dir: Path,
    date_col: str,
    dedup_keys: List[str],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    grouped: Dict[str, List[pd.DataFrame]] = {}

    for f in files:
        code, df = load_and_tag(f, date_col)
        grouped.setdefault(code, []).append(df)

    report_rows = []
    for code, dfs in grouped.items():
        merged = pd.concat(dfs, ignore_index=True)
        before = len(merged)
        merged = merged.sort_values(date_col)

        keys = ensure_dedup_keys(merged, dedup_keys)
        merged = merged.drop_duplicates(subset=keys, keep="last").reset_index(drop=True)
        after = len(merged)

        out_file = output_dir / f"{code}.csv"
        merged.to_csv(out_file, index=False)

        report_rows.append(
            {
                "code": code,
                "files_merged": len(dfs),
                "rows_before": before,
                "rows_after": after,
                "dedup_removed": before - after,
                "start_time": merged[date_col].min(),
                "end_time": merged[date_col].max(),
                "output_file": str(out_file),
            }
        )
        print(
            f"[OK] code={code}, files={len(dfs)}, rows_before={before}, "
            f"rows_after={after}, output={out_file.name}"
        )

    report = pd.DataFrame(report_rows).sort_values("code")
    report_file = output_dir / "merge_report.csv"
    report.to_csv(report_file, index=False)
    print(f"\nDone. Merged files: {len(report_rows)}")
    print(f"Report: {report_file}")
    return report_file


def main() -> None:
    args = parse_args()
    files = collect_csv_files(args.inputs)
    if not files:
        raise FileNotFoundError("No csv files found from --inputs")
    merge_by_code(files, Path(args.output_dir).resolve(), args.date_col, args.dedup_keys)


if __name__ == "__main__":
    main()
