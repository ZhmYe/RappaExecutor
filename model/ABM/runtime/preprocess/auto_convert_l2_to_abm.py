#!/usr/bin/env python3
"""
Convert SHL2/SZL2 TAQ raw csv files to ABM-ready 1min csv.

Usage:
  python auto_convert_l2_to_abm.py \
    --inputs SHL2_TAQ_600000_202205.csv SZL2_TAQ_000001_202205.csv \
    --output-dir output_abm
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List

import pandas as pd


SH_COLUMNS = [
    "stockid",
    "TRDDATE",
    "date",
    "preclose",
    "open",
    "high",
    "low",
    "close",
    "INSTRUSTATUS",
    "NOOFFERLVL",
    "sale10",
    "sale9",
    "sale8",
    "sale7",
    "sale6",
    "sale5",
    "sale4",
    "sale3",
    "sale2",
    "sale1",
    "buy1",
    "buy2",
    "buy3",
    "buy4",
    "buy5",
    "buy6",
    "buy7",
    "buy8",
    "buy9",
    "buy10",
    "NOBIDLVL",
    "sc10",
    "sc9",
    "sc8",
    "sc7",
    "sc6",
    "sc5",
    "sc4",
    "sc3",
    "sc2",
    "sc1",
    "bc1",
    "bc2",
    "bc3",
    "bc4",
    "bc5",
    "bc6",
    "bc7",
    "bc8",
    "bc9",
    "bc10",
    "NUMTRADES",
    "TOTALVOLUME",
    "TURNOVER",
]

SZ_COLUMNS = [
    "stockid",
    "TRDDATE",
    "date",
    "preclose",
    "open",
    "high",
    "low",
    "close",
    "NUMTRADES",
    "CT",
    "TOTALVOLUME",
    "CQ",
    "TURNOVER",
    "CM",
    "PERatio1",
    "PERatio2",
    "TotalSellOrderVolume",
    "WtAvgSellPrice",
    "SellLevelNo",
    "sale10",
    "sale9",
    "sale8",
    "sale7",
    "sale6",
    "sale5",
    "sale4",
    "sale3",
    "sale2",
    "sale1",
    "sc10",
    "sc9",
    "sc8",
    "sc7",
    "sc6",
    "sc5",
    "sc4",
    "sc3",
    "sc2",
    "sc1",
    "TotalBuyOrderVolume",
    "WtAvgBuyPrice",
    "BuyLevelNo",
    "buy1",
    "buy2",
    "buy3",
    "buy4",
    "buy5",
    "buy6",
    "buy7",
    "buy8",
    "buy9",
    "buy10",
    "bc1",
    "bc2",
    "bc3",
    "bc4",
    "bc5",
    "bc6",
    "bc7",
    "bc8",
    "bc9",
    "bc10",
]

TARGET_COLUMNS = SH_COLUMNS

NUMERIC_COLUMNS = [
    "preclose",
    "open",
    "high",
    "low",
    "close",
    "NUMTRADES",
    "TOTALVOLUME",
    "TURNOVER",
] + [f"buy{i}" for i in range(1, 11)] + [f"sale{i}" for i in range(1, 11)] + [f"bc{i}" for i in range(1, 11)] + [
    f"sc{i}" for i in range(1, 11)
]


def detect_market(path: Path) -> str:
    name = path.name.upper()
    if name.startswith("SHL2_TAQ_"):
        return "SH"
    if name.startswith("SZL2_TAQ_"):
        return "SZ"
    raise ValueError(f"Unsupported file prefix: {path.name}")


def extract_code(path: Path) -> str:
    m = re.search(r"_(\d{6})_", path.name)
    return m.group(1) if m else path.stem


def defreq_rule() -> Dict[str, str]:
    rule: Dict[str, str] = {
        "stockid": "last",
        "TRDDATE": "last",
        "INSTRUSTATUS": "last",
        "NOOFFERLVL": "last",
        "NOBIDLVL": "last",
        "preclose": "last",
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "NUMTRADES": "last",
        "TOTALVOLUME": "last",
        "TURNOVER": "last",
    }
    for i in range(1, 11):
        rule[f"buy{i}"] = "last"
        rule[f"sale{i}"] = "last"
        rule[f"bc{i}"] = "last"
        rule[f"sc{i}"] = "last"
    return rule


def read_raw(path: Path, market: str) -> pd.DataFrame:
    schema = SH_COLUMNS if market == "SH" else SZ_COLUMNS
    df = pd.read_csv(path, header=None)
    if df.shape[1] < len(schema):
        raise ValueError(f"{path.name}: expected >= {len(schema)} cols, got {df.shape[1]}")
    df = df.iloc[:, : len(schema)].copy()
    df.columns = schema
    return df


def normalize_to_target(df: pd.DataFrame, market: str) -> pd.DataFrame:
    out = df.copy()
    if market == "SZ":
        out["INSTRUSTATUS"] = out.get("INSTRUSTATUS", pd.NA)
        out["NOOFFERLVL"] = out.get("SellLevelNo", pd.NA)
        out["NOBIDLVL"] = out.get("BuyLevelNo", pd.NA)

    for col in TARGET_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA
    out = out[TARGET_COLUMNS]
    return out


def filter_sessions(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"])
    hm = out["date"].dt.time
    s1 = pd.to_datetime("09:30:00.000").time()
    e1 = pd.to_datetime("11:30:00.000").time()
    s2 = pd.to_datetime("13:00:00.000").time()
    e2 = pd.to_datetime("15:00:00.000").time()
    out = out[((hm > s1) & (hm <= e1)) | ((hm > s2) & (hm <= e2))]
    return out


def convert_numeric(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in NUMERIC_COLUMNS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def to_1min(df: pd.DataFrame) -> pd.DataFrame:
    agg_rule = {k: v for k, v in defreq_rule().items() if k in df.columns}
    out = (
        df.set_index("date")
        .resample("1min", closed="right", label="right")
        .agg(agg_rule)
        .reset_index()
    )
    out = out.dropna(subset=["stockid"])
    return out


def post_clean(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["stockid"] = pd.to_numeric(out["stockid"], errors="coerce").astype("Int64")
    out = out.dropna(subset=["stockid"]).copy()
    out["stockid"] = out["stockid"].astype("int64")

    if "NUMTRADES" in out.columns:
        out["NUMTRADES"] = pd.to_numeric(out["NUMTRADES"], errors="coerce").fillna(0).astype("int64")

    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out["close"] = out["close"].replace(0, pd.NA).ffill()

    if len(out) > 0:
        first_preclose = out["preclose"].iloc[0]
        out["preclose"] = out["close"].shift(1)
        out.loc[out.index[0], "preclose"] = first_preclose

    return out


def sanity_summary(df: pd.DataFrame) -> Dict[str, float]:
    b1 = pd.to_numeric(df["buy1"], errors="coerce")
    s1 = pd.to_numeric(df["sale1"], errors="coerce")
    mask = b1.notna() & s1.notna() & (b1 > 0) & (s1 > 0)
    spread_ok = float((s1[mask] >= b1[mask]).mean()) if mask.any() else float("nan")
    close_ok = float((pd.to_numeric(df["close"], errors="coerce") > 0).mean()) if len(df) else float("nan")
    return {"rows": float(len(df)), "spread_ok_ratio": spread_ok, "close_pos_ratio": close_ok}


def convert_one(path: Path, out_dir: Path) -> Path:
    market = detect_market(path)
    code = extract_code(path)
    df = read_raw(path, market)
    df = normalize_to_target(df, market)
    df = filter_sessions(df)
    df = convert_numeric(df)
    df = to_1min(df)
    df = post_clean(df)
    out_path = out_dir / f"{code}.csv"
    df.to_csv(out_path, index=False)

    info = sanity_summary(df)
    print(
        f"[OK] {path.name} -> {out_path.name} | rows={int(info['rows'])}, "
        f"spread_ok={info['spread_ok_ratio']:.3f}, close_pos={info['close_pos_ratio']:.3f}"
    )
    return out_path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Convert SHL2/SZL2 TAQ to ABM-ready csv")
    p.add_argument("--inputs", nargs="+", required=True, help="Input SHL2/SZL2 csv paths")
    p.add_argument("--output-dir", required=True, help="Output folder")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    for ip in args.inputs:
        convert_one(Path(ip).resolve(), out_dir)
    print(f"\nDone. Output dir: {out_dir}")


if __name__ == "__main__":
    main()
