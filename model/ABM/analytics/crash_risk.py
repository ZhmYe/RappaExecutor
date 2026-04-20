from typing import Dict

import pandas as pd

from model.ABM.analytics.common import round_or_none
from model.ABM.analytics.constants import CRASH_RISK_BANDS
from model.ABM.analytics.io import read_csv_frame, read_json


def build_crash_risk_payload(predict_root) -> Dict:
    predict_df = read_csv_frame(predict_root / "predict_fv.csv")
    predict_meta = read_json(predict_root / "predict_fv_meta.json")

    probability = 0.0
    forecast_series = []
    if not predict_df.empty:
        working = predict_df.copy()
        working["Forecast_Time"] = pd.to_datetime(working["Forecast_Time"], errors="coerce")
        working = working.dropna(subset=["Forecast_Time"])
        if not working.empty:
            for column in [
                "Predicted_Price",
                "Prob_Drop_3pct",
                "Prob_Drop_5pct",
                "Prob_Drop_10pct",
                "Crash_Prob",
            ]:
                if column in working.columns:
                    working[column] = pd.to_numeric(working[column], errors="coerce")
            working = working.sort_values("Forecast_Time")

            latest_crash = working["Crash_Prob"].dropna()
            if not latest_crash.empty:
                probability = float(latest_crash.iloc[-1])
            elif "Prob_Drop_10pct" in working.columns:
                latest_drop = working["Prob_Drop_10pct"].dropna()
                if not latest_drop.empty:
                    probability = float(latest_drop.iloc[-1])

            for _, row in working.iterrows():
                forecast_series.append(
                    {
                        "date": row["Forecast_Time"].strftime("%Y-%m-%d"),
                        "predictedPrice": round_or_none(row.get("Predicted_Price")),
                        "probDrop3pct": round_or_none(row.get("Prob_Drop_3pct")),
                        "probDrop5pct": round_or_none(row.get("Prob_Drop_5pct")),
                        "probDrop10pct": round_or_none(row.get("Prob_Drop_10pct")),
                        "crashProb": round_or_none(row.get("Crash_Prob")),
                    }
                )

    probability = max(0.0, min(1.0, probability))
    return {
        "summary": {"predictionProbability": round(probability, 6), "chartConfig": CRASH_RISK_BANDS},
        "topRiskList": [],
        "forecastSeries": forecast_series,
        "meta": predict_meta,
    }
