"""Çevrimdışı fiyat araştırması: küçük ağ ve sabit karşılaştırmalar.

Bu deney emir üretmez, API çağırmaz ve mevcut botu kullanmaz.
"""
import argparse
import hashlib
import json
import math
import random
from datetime import timedelta
from pathlib import Path

from experiments.market_research import build_splits, load_prices, metrics, research
from experiments.neural_demo import TinyNetwork

MODEL_SEED = 7
SAMPLE_SEED = 3
STEPS = 1500
BATCH_SIZE = 32
RATE = 0.1


def fit_scaler(examples):
    """İki özelliğin ortalama ve ölçeğini yalnızca eğitim örneklerinden al."""
    if not examples:
        raise ValueError("Eğitim örnekleri boş olamaz")
    means = tuple(sum(e.features[i] for e in examples) / len(examples) for i in range(2))
    variances = tuple(sum((e.features[i] - means[i]) ** 2 for e in examples) / len(examples)
                      for i in range(2))
    scales = tuple(math.sqrt(v) if v > 0 else 1.0 for v in variances)
    if not all(math.isfinite(x) for x in (*means, *scales)):
        raise ValueError("Eğitim ölçeği sonlu olmalı")
    return means, scales


def transform(features, means, scales):
    transformed = tuple((features[i] - means[i]) / scales[i] for i in range(2))
    if not all(math.isfinite(x) for x in transformed):
        raise ValueError("Dönüştürülmüş özellikler sonlu olmalı")
    return transformed


def fit_neural(examples):
    """Sabit tohum/ayarlarla eğitim; doğrulama ve test verisi almaz."""
    means, scales = fit_scaler(examples)
    rows = [(*transform(e.features, means, scales), e.label) for e in examples]
    model = TinyNetwork(seed=MODEL_SEED)
    rng = random.Random(SAMPLE_SEED)
    for _ in range(STEPS):
        model.train_step([rows[rng.randrange(len(rows))] for _ in range(BATCH_SIZE)], rate=RATE)
    return model, means, scales


def compare(prices, *, lookback=6, horizon=3):
    """Önceden sabit bölme ve aynı örneklerle temel modeli/ağı karşılaştır."""
    parts = build_splits(prices, lookback=lookback, horizon=horizon,
                         train_end=len(prices) * 6 // 10,
                         validation_end=len(prices) * 8 // 10)
    model, means, scales = fit_neural(parts["train"])
    report = research(prices, lookback=lookback, horizon=horizon)
    for name, examples in parts.items():
        report["sections"][name]["neural"] = metrics(
            examples, lambda e: model.predict(*transform(e.features, means, scales)))
    report["neural_settings"] = {
        "hidden_neurons": len(model.weights), "model_seed": MODEL_SEED,
        "sample_seed": SAMPLE_SEED, "steps": STEPS, "batch_size": BATCH_SIZE,
        "learning_rate": RATE, "training_feature_means": means,
        "training_feature_scales": scales,
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="Ağsız sinir ağı karşılaştırması")
    parser.add_argument("--prices", type=Path, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--data-kind", choices=("synthetic", "historical"), required=True)
    parser.add_argument("--interval-seconds", type=int, default=3600)
    parser.add_argument("--lookback", type=int, default=6)
    parser.add_argument("--horizon", type=int, default=3)
    args = parser.parse_args()
    try:
        prices = load_prices(args.prices, args.symbol, timedelta(seconds=args.interval_seconds))
        result = compare(prices, lookback=args.lookback, horizon=args.horizon)
        result.update(symbol=args.symbol, data_kind=args.data_kind,
                      interval_seconds=args.interval_seconds,
                      input_sha256=hashlib.sha256(args.prices.read_bytes()).hexdigest())
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Hata: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
