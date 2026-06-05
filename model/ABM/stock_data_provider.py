import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from utils.function.func import get_project_root


DEFAULT_REMOTE_DB = "dfs://ods_tsdb_d_hash20_csmar"
DEFAULT_REMOTE_TABLE = "l1_trdmin1_sh"


@dataclass
class StockDataWindow:
    start_date: str
    end_date: str


@dataclass
class StockDataRequest:
    stock_code: str
    window: StockDataWindow


def normalize_code(code: str) -> str:
    text = str(code or "").strip()
    if text.isdigit() and len(text) < 6:
        return text.zfill(6)
    return text


def load_executor_config() -> Dict[str, Any]:
    config_path = Path(get_project_root()).resolve() / "config.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            parsed = json.load(f)
            return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def config_value(config: Dict[str, Any], key: str, default: Any = "") -> Any:
    value = config.get(key)
    if value is None or str(value).strip() == "":
        return default
    return value


def stock_data_source(config: Dict[str, Any]) -> str:
    mode = str(config_value(config, "ABMStockDataSource", "auto")).strip().lower()
    if mode not in {"local", "dolphindb", "auto"}:
        return "auto"
    return mode


def normalize_data_window(params: Dict[str, Any], config: Dict[str, Any]) -> StockDataWindow:
    start = str(params.get("dataStartDate") or params.get("startDate") or "").strip()
    end = str(params.get("dataEndDate") or params.get("endDate") or "").strip()
    if not start and not end:
        offset = int(config_value(config, "ABMRemoteDefaultEndOffsetDays", 1))
        target = date.today() - timedelta(days=max(1, offset))
        day = target.strftime("%Y-%m-%d")
        return StockDataWindow(day, day)
    if not start:
        start = end
    if not end:
        end = start
    start_dt = parse_date(start)
    end_dt = parse_date(end)
    if end_dt < start_dt:
        raise ValueError("dataEndDate before dataStartDate")
    return StockDataWindow(start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))


def parse_date(value: str) -> date:
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"invalid date {value!r}, expected YYYY-MM-DD")


def dolphin_date(value: str) -> str:
    return value.replace("-", ".")


def normalize_stock_minute_df(df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
    if df is None or df.empty:
        raise ValueError("remote stock data is empty")

    time_col = first_existing(df, ["TradingTime", "TrdaingTime", "date", "Time"])
    close_col = first_existing(df, ["ClosePrice", "close", "Close", "Price", "price"])
    if not time_col:
        raise ValueError("remote stock data missing TradingTime/TrdaingTime/date/Time")
    if not close_col:
        raise ValueError("remote stock data missing ClosePrice/close")

    out = pd.DataFrame()
    out["date"] = pd.to_datetime(df[time_col], errors="coerce")
    out["stockid"] = normalize_code(stock_code)
    out["open"] = numeric_or_default(df, ["OpenPrice", "open", "Open"], close_col)
    out["high"] = numeric_or_default(df, ["HighPrice", "high", "High"], close_col)
    out["low"] = numeric_or_default(df, ["LowPrice", "low", "Low"], close_col)
    out["close"] = pd.to_numeric(df[close_col], errors="coerce")
    out["TOTALVOLUME"] = numeric_or_zero(df, ["Volume", "TOTALVOLUME", "volume"])
    out["TURNOVER"] = numeric_or_zero(df, ["Amount", "TURNOVER", "amount"])

    out = out.dropna(subset=["date", "close"]).copy()
    out = out[out["close"] > 0]
    if out.empty:
        raise ValueError("remote stock data has no valid close rows")
    out = out.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    out["date"] = out["date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return out[["date", "stockid", "open", "high", "low", "close", "TOTALVOLUME", "TURNOVER"]]


def first_existing(df: pd.DataFrame, names: list[str]) -> Optional[str]:
    for name in names:
        if name in df.columns:
            return name
    return None


def numeric_or_default(df: pd.DataFrame, candidates: list[str], default_col: str) -> pd.Series:
    col = first_existing(df, candidates)
    if col:
        return pd.to_numeric(df[col], errors="coerce")
    return pd.to_numeric(df[default_col], errors="coerce")


def numeric_or_zero(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    col = first_existing(df, candidates)
    if col:
        return pd.to_numeric(df[col], errors="coerce").fillna(0)
    return pd.Series([0] * len(df), index=df.index)


class DolphinDBStockDataProvider:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    def load(self, request: StockDataRequest) -> pd.DataFrame:
        try:
            import dolphindb as ddb
        except Exception as exc:
            raise RuntimeError(f"import dolphindb failed: {exc}") from exc

        host = str(config_value(self.config, "ABMRemoteDBHost", "192.168.198.76"))
        port = int(config_value(self.config, "ABMRemoteDBPort", 8904))
        user = str(config_value(self.config, "ABMRemoteDBUser", "maoshuoyu"))
        password = str(config_value(self.config, "ABMRemoteDBPassword", "Swhy1234!@#$"))
        db_name = str(config_value(self.config, "ABMRemoteDBName", DEFAULT_REMOTE_DB))
        table_name = str(config_value(self.config, "ABMRemoteTableName", DEFAULT_REMOTE_TABLE))

        symbol = f"`{normalize_code(request.stock_code)}"
        start = dolphin_date(request.window.start_date)
        end = dolphin_date(request.window.end_date)
        script = f"""
inputDBName = "{db_name}"
inputTBName = "{table_name}"
quotes = loadTable(inputDBName, inputTBName)
select * from quotes where Symbol={symbol} and TradingDate between {start}:{end}
"""
        session = ddb.session()
        session.connect(host=host, port=port, userid=user, password=password, keepAliveTime=300)
        df = session.run(script)
        return normalize_stock_minute_df(df, request.stock_code)


def materialize_remote_stock_csv(params: Dict[str, Any], output_path: Path) -> Path:
    config = load_executor_config()
    stock_code = normalize_code(
        params.get("stockCode")
        or (params.get("evaluation", {}) or {}).get("code")
        or params.get("dataset")
        or output_path.stem
    )
    window = normalize_data_window(params, config)
    provider = DolphinDBStockDataProvider(config)
    df = provider.load(StockDataRequest(stock_code=stock_code, window=window))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path.resolve()


def configured_data_source_mode() -> str:
    return stock_data_source(load_executor_config())
