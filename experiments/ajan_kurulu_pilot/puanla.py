"""Score the fixed pilot forecasts against daily closes; no external calls."""
import argparse
import csv
import hashlib
import json
import math
from datetime import date, timedelta
from pathlib import Path

CASES = {"1A": ("BTCUSDT", "2022-07-01"), "1B": ("ETHUSDT", "2022-07-01"),
         "2A": ("BTCUSDT", "2023-09-01"), "2B": ("ETHUSDT", "2023-09-01"),
         "3A": ("BTCUSDT", "2024-09-01"), "3B": ("ETHUSDT", "2024-09-01")}
ROLES = ("bull", "bear", "risk")


def validate_forecasts(data):
    rows = data["episodes"]
    if len(rows) != len(CASES) or {r["id"] for r in rows} != set(CASES):
        raise ValueError("All forecast IDs must be present exactly once")
    for row in rows:
        for role in ROLES:
            p = row[role]
            if isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1:
                raise ValueError("Probabilities must be finite numbers in [0,1]")
    return rows


def load_prices(path):
    prices = {}
    previous = None
    with Path(path).open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            day = date.fromisoformat(row["gun"])
            value = float(row["kapanis"])
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Invalid price")
            if previous is not None and day != previous + timedelta(days=1):
                raise ValueError("Daily prices must be contiguous and ordered")
            prices[day] = value
            previous = day
    return prices


def evaluate(forecasts, prices):
    results = []
    for row in validate_forecasts(forecasts):
        symbol, text = CASES[row["id"]]
        day = date.fromisoformat(text)
        series = prices[symbol]
        ret = series[day + timedelta(days=20)] / series[day] - 1
        actual = int(ret > 0)
        p = sum(row[role] for role in ROLES) / len(ROLES)
        results.append({"id": row["id"], "symbol": symbol, "date": text,
                        "return_20d": ret, "actual_up": actual, "mean_probability": p})
    return {"count": len(results), "forecasts": results,
            "mean_brier": sum((r["mean_probability"] - r["actual_up"]) ** 2 for r in results) / len(results),
            "constant_half_brier": 0.25}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--forecasts", type=Path, default=Path(__file__).with_name("tahminler.json"))
    args = parser.parse_args()
    forecast = json.loads(args.forecasts.read_text(encoding="utf-8"))
    paths = {s: args.data / (s + ".csv") for s in ("BTCUSDT", "ETHUSDT")}
    report = evaluate(forecast, {s: load_prices(p) for s, p in paths.items()})
    report["sha256"] = {s: hashlib.sha256(p.read_bytes()).hexdigest() for s, p in paths.items()}
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
