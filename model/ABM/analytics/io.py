import csv
import json
from pathlib import Path
from typing import Any, Dict

import pandas as pd


def read_csv_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"analysis file not found: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def read_csv_dict(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"analysis file not found: {path}")
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        columns = list(reader.fieldnames or [])
    return {"path": str(path), "columns": columns, "rows": rows}


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"analysis file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
