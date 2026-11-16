"""Çevrimdışı zaman sıralı fiyat araştırması; emir ve API çağrısı içermez."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path


@dataclass(frozen=True)
class Price:
    time: datetime
    close: Decimal


@dataclass(frozen=True)
class Example:
    index: int
    target_index: int
    time: datetime
    target_time: datetime
    features: tuple[float, float]
    label: int


def load_prices(path: Path, symbol: str, interval: timedelta) -> list[Price]:
    """Başlıklı timestamp,symbol,close CSV; eksik, yinelenen veya karışık saatleri reddet."""
    if not symbol or interval <= timedelta(0):
        raise ValueError("Sembol ve pozitif mum aralığı gerekli")
    result = []
    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if not {"timestamp", "symbol", "close"}.issubset(reader.fieldnames or []):
            raise ValueError("CSV alanları: timestamp,symbol,close")
        for row in reader:
            if row["symbol"] != symbol:
                continue
            try:
                ts = datetime.fromisoformat(row["timestamp"])
                close = Decimal(row["close"])
            except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
                raise ValueError("Geçersiz zaman veya fiyat") from exc
            if ts.utcoffset() is None or not close.is_finite() or close <= 0:
                raise ValueError("Saat dilimi ve pozitif sonlu fiyat gerekli")
            if result and ts - result[-1].time != interval:
                raise ValueError("Zamanlar sıralı, benzersiz ve eksiksiz olmalı")
            result.append(Price(ts, close))
    if not result:
        raise ValueError("Sembol için veri bulunamadı")
    return result


def build_splits(prices: list[Price], *, lookback: int, horizon: int,
                 train_end: int, validation_end: int):
    """Hedefi bölüm sınırını aşan örnekleri at; geçmiş özellikleri koru."""
    n = len(prices)
    if (type(lookback) is not int or type(horizon) is not int
            or type(train_end) is not int or type(validation_end) is not int
            or lookback < 2 or horizon < 1
            or not 0 < train_end < validation_end < n):
        raise ValueError("Geçersiz bakış aralığı, ufuk veya bölüm sınırları")
    interval = None
    for i, item in enumerate(prices):
        if item.time.utcoffset() is None or not item.close.is_finite() or item.close <= 0:
            raise ValueError("Saat dilimi ve pozitif sonlu fiyat gerekli")
        if i:
            step = item.time - prices[i - 1].time
            if step <= timedelta(0) or (interval is not None and step != interval):
                raise ValueError("Zamanlar sıralı, benzersiz ve eşit aralıklı olmalı")
            interval = step
    parts = {"train": [], "validation": [], "test": []}
    for i in range(lookback, n - horizon):
        target = i + horizon
        if i < train_end and target < train_end:
            part = "train"
        elif train_end <= i < validation_end and target < validation_end:
            part = "validation"
        elif i >= validation_end:
            part = "test"
        else:
            continue  # hedefi sonraki bölüme uzayan örnekler kullanılmaz
        now = prices[i].close
        features = (float((now / prices[i - 1].close - 1) * 100),
                    float((now / prices[i - lookback].close - 1) * 100))
        if not all(math.isfinite(v) for v in features):
            raise ValueError("Özellikler sonlu olmalı")
        parts[part].append(Example(i, target, prices[i].time, prices[target].time,
                                   features, int(prices[target].close > now)))
    if any(not examples for examples in parts.values()):
        raise ValueError("Her veri bölümünde en az bir örnek gerekli")
    return parts


def probability(weights, features):
    z = weights[0] + weights[1] * features[0] + weights[2] * features[1]
    return 1 / (1 + math.exp(-max(-40, min(40, z))))


def train_model(examples, epochs=300, rate=0.02):
    """Sabit ayarlı küçük lojistik karşılaştırma modeli; yalnızca eğitim verisi."""
    weights = [0.0, 0.0, 0.0]
    for _ in range(epochs):
        gradients = [0.0, 0.0, 0.0]
        for example in examples:
            error = probability(weights, example.features) - example.label
            gradients[0] += error
            gradients[1] += error * example.features[0]
            gradients[2] += error * example.features[1]
        weights = [w - rate * g / len(examples) for w, g in zip(weights, gradients)]
    return weights


def metrics(examples, predict):
    probabilities = [predict(example) for example in examples]
    if any(not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities):
        raise ValueError("Olasılık 0 ile 1 arasında sonlu olmalı")
    count = len(examples)
    return {"count": count,
            "accuracy": sum((p >= 0.5) == bool(e.label)
                            for p, e in zip(probabilities, examples)) / count,
            "brier": sum((p - e.label) ** 2 for p, e in zip(probabilities, examples)) / count}


def research(prices, *, lookback=6, horizon=3):
    parts = build_splits(prices, lookback=lookback, horizon=horizon,
                         train_end=len(prices) * 6 // 10,
                         validation_end=len(prices) * 8 // 10)
    weights = train_model(parts["train"])
    prevalence = sum(e.label for e in parts["train"]) / len(parts["train"])
    majority = float(prevalence >= 0.5)
    reports = {}
    for name, examples in parts.items():
        reports[name] = {
            "start": examples[0].time.isoformat(),
            "last_decision": examples[-1].time.isoformat(),
            "last_target": examples[-1].target_time.isoformat(),
            "logistic": metrics(examples, lambda e: probability(weights, e.features)),
            "majority_from_train": metrics(examples, lambda e: majority),
            "prevalence_from_train": metrics(examples, lambda e: prevalence),
            "constant_half": metrics(examples, lambda e: 0.5),
        }
    return {"lookback_bars": lookback, "horizon_bars": horizon,
            "target": "ufuktaki kapanış > karar anı kapanışı",
            "model": "lojistik temel model; sabit ayarlar, eğitim bölümüyle eğitildi",
            "sections": reports}


def main():
    parser = argparse.ArgumentParser(description="Ağsız, emir vermeyen araştırma")
    parser.add_argument("--prices", type=Path, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--interval-seconds", type=int, default=3600)
    parser.add_argument("--lookback", type=int, default=6)
    parser.add_argument("--horizon", type=int, default=3)
    args = parser.parse_args()
    try:
        prices = load_prices(args.prices, args.symbol, timedelta(seconds=args.interval_seconds))
        result = research(prices, lookback=args.lookback, horizon=args.horizon)
        result["symbol"] = args.symbol
        result["interval_seconds"] = args.interval_seconds
        result["input_sha256"] = hashlib.sha256(args.prices.read_bytes()).hexdigest()
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Hata: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
