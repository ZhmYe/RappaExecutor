from typing import Dict

import pandas as pd

from model.ABM.analytics.io import read_csv_frame


def build_price_synthesis_payload(abm_root) -> Dict:
    df = read_csv_frame(abm_root / "kline_ohlcv.csv")
    if df.empty:
        return {"tradingDates": [], "klineData": [], "volData": []}

    working = df.copy()
    working["Timestamp"] = pd.to_datetime(working["Timestamp"], errors="coerce")
    working = working.dropna(subset=["Timestamp"])
    if working.empty:
        return {"tradingDates": [], "klineData": [], "volData": []}

    for column in ["Open", "High", "Low", "Close", "Volume"]:
        working[column] = pd.to_numeric(working[column], errors="coerce").fillna(0.0)
    working = working.sort_values("Timestamp")

    trading_dates = working["Timestamp"].dt.strftime("%Y-%m-%d").tolist()
    kline_data = []
    vol_data = []
    up_color = "#ef4444"
    down_color = "#22c55e"

    for _, row in working.iterrows():
        open_price = round(float(row["Open"]), 4)
        high_price = round(float(row["High"]), 4)
        low_price = round(float(row["Low"]), 4)
        close_price = round(float(row["Close"]), 4)
        volume = round(float(row["Volume"]), 4)
        color = up_color if close_price >= open_price else down_color

        kline_data.append(
            {
                "value": [open_price, close_price, low_price, high_price],
                "itemStyle": {
                    "color": color,
                    "color0": color,
                    "borderColor": color,
                    "borderColor0": color,
                    "borderWidth": 1,
                },
            }
        )
        vol_data.append({"value": volume, "itemStyle": {"color": color}})

    return {"tradingDates": trading_dates, "klineData": kline_data, "volData": vol_data}
