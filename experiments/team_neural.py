"""Offline comparison on the team's daily data; no orders or external calls."""
import argparse
import csv
import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from experiments.market_neural import fit_neural, transform
from experiments.market_research import Example, Price, metrics, probability, train_model

HORIZON = 20
SECTIONS = (("train", "2020-01-01", "2022-12-31"),
            ("validation", "2023-01-01", "2023-12-31"),
            ("test", "2024-01-01", "2026-10-31"))


def load_daily(path):
    prices = []
    with Path(path).open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"gun", "kapanis"}.issubset(reader.fieldnames or []):
            raise ValueError("Expected gun,kapanis CSV")
        for row in reader:
            try:
                time = datetime.fromisoformat(row["gun"]).replace(tzinfo=timezone.utc)
                close = Decimal(row["kapanis"])
            except (ValueError, InvalidOperation, TypeError) as exc:
                raise ValueError("Invalid date or price") from exc
            if not close.is_finite() or close <= 0:
                raise ValueError("Invalid price")
            if prices and time - prices[-1].time != timedelta(days=1):
                raise ValueError("Dates must be consecutive and increasing")
            prices.append(Price(time, close))
    return prices


def build_examples(prices, feature_set):
    """Features end at decision close; target stays inside its time section."""
    if feature_set not in ("original", "team"):
        raise ValueError("Unknown features")
    parts = {name: [] for name, _, _ in SECTIONS}
    for i in range(49, len(prices) - HORIZON):
        day = prices[i].time.date().isoformat()
        target_day = prices[i + HORIZON].time.date().isoformat()
        name = next((n for n, start, end in SECTIONS if start <= day <= end and target_day <= end), None)
        if name is None:
            continue
        close = prices[i].close
        if feature_set == "team":
            sma50 = sum(p.close for p in prices[i - 49:i + 1]) / 50
            features = (float((close / prices[i - 30].close - 1) * 100),
                        float((close / sma50 - 1) * 100))
        else:
            features = (float((close / prices[i - 1].close - 1) * 100),
                        float((close / prices[i - 6].close - 1) * 100))
        parts[name].append(Example(i, i + HORIZON, prices[i].time,
                                   prices[i + HORIZON].time, features,
                                   int(prices[i + HORIZON].close > close)))
    if any(not items for items in parts.values()):
        raise ValueError("Every time section needs data")
    return parts


def compare(prices, feature_set):
    parts = build_examples(prices, feature_set)
    train = parts["train"]
    network, means, scales = fit_neural(train)
    standardized = [replace(e, features=transform(e.features, means, scales)) for e in train]
    weights = train_model(standardized)
    rate = sum(e.label for e in train) / len(train)
    results = {}
    for name, examples in parts.items():
        results[name] = {
            "first": examples[0].time.isoformat(),
            "last_target": examples[-1].target_time.isoformat(),
            "neural": metrics(examples, lambda e: network.predict(*transform(e.features, means, scales))),
            "logistic": metrics(examples, lambda e: probability(weights, transform(e.features, means, scales))),
            "training_rate": metrics(examples, lambda e: rate),
            "constant_half": metrics(examples, lambda e: 0.5),
        }
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices", required=True, type=Path)
    parser.add_argument("--symbol", required=True)
    args = parser.parse_args()
    prices = load_daily(args.prices)
    report = {"symbol": args.symbol, "sha256": hashlib.sha256(args.prices.read_bytes()).hexdigest(),
              "horizon_days": HORIZON, "sections": SECTIONS,
              "original": compare(prices, "original"), "team": compare(prices, "team")}
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
