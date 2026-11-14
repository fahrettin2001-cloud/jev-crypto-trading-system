"""Zaman ilerledikçe yeniden eğitim; işlem ve ağ erişimi yok."""
import argparse
import hashlib
import json
from datetime import timedelta
from pathlib import Path

from experiments.market_neural import fit_neural, transform
from experiments.market_research import (load_prices, make_example, metrics,
                                         probability, train_model, validate_series)


def make_windows(prices, *, lookback=6, horizon=3):
    """Son %20'yi ayır; kalan %80 içinde genişleyen eğitim ve ayrı pencereler."""
    if type(lookback) is not int or type(horizon) is not int or lookback < 2 or horizon < 1:
        raise ValueError("Geçersiz geçmiş uzunluğu veya ufuk")
    n = len(prices)
    reserved_start = n * 8 // 10
    research_prices = prices[:reserved_start]
    validate_series(research_prices)
    start = n * 4 // 10
    window_size = n // 10
    if window_size <= horizon or start <= lookback + horizon:
        raise ValueError("Veri, ufuk ve dört araştırma penceresi için yetersiz")
    windows = []
    while start + window_size <= reserved_start:
        end = start + window_size
        # Eğitim hedefi ilk değerlendirme zamanından kesinlikle önce bitmeli.
        train = [make_example(research_prices, i, lookback, horizon)
                 for i in range(lookback, start - horizon)]
        evaluation = [make_example(research_prices, i, lookback, horizon)
                      for i in range(start, end - horizon)]
        if not train or not evaluation:
            raise ValueError("Her dönemde eğitim ve değerlendirme örneği gerekli")
        windows.append((train, evaluation))
        start = end
    if not windows:
        raise ValueError("Değerlendirme dönemi bulunamadı")
    return windows, reserved_start


def run_walk_forward(prices, *, lookback=6, horizon=3):
    windows, reserved_start = make_windows(prices, lookback=lookback, horizon=horizon)
    report = []
    for number, (training, evaluation) in enumerate(windows, 1):
        model, mean, scale = fit_neural(training)
        logistic = train_model(training)
        rate = sum(e.label for e in training) / len(training)
        report.append({
            "window": number,
            "train_count": len(training),
            "train_first": training[0].time.isoformat(),
            "last_train_decision": training[-1].time.isoformat(),
            "last_train_target": training[-1].target_time.isoformat(),
            "eval_first": evaluation[0].time.isoformat(),
            "eval_last": evaluation[-1].time.isoformat(),
            "eval_last_target": evaluation[-1].target_time.isoformat(),
            "neural": metrics(evaluation, lambda e: model.predict(*transform(e.features, mean, scale))),
            "logistic": metrics(evaluation, lambda e: probability(logistic, e.features)),
            "train_prevalence": metrics(evaluation, lambda e: rate),
            "constant_half": metrics(evaluation, lambda e: 0.5),
        })
    return {"lookback_bars": lookback, "horizon_bars": horizon,
            "reserved_bars": len(prices) - reserved_start,
            "reserved_first": prices[reserved_start].time.isoformat(),
            "reserved_evaluated": False, "windows": report}


def main():
    parser = argparse.ArgumentParser(description="Çevrimdışı zaman sıralı araştırma")
    parser.add_argument("--prices", type=Path, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--data-kind", required=True, choices=("synthetic", "historical"))
    parser.add_argument("--interval-seconds", type=int, default=3600)
    parser.add_argument("--lookback", type=int, default=6)
    parser.add_argument("--horizon", type=int, default=3)
    args = parser.parse_args()
    try:
        prices = load_prices(args.prices, args.symbol, timedelta(seconds=args.interval_seconds))
        report = run_walk_forward(prices, lookback=args.lookback, horizon=args.horizon)
        report.update(symbol=args.symbol, data_kind=args.data_kind,
                      interval_seconds=args.interval_seconds,
                      input_sha256=hashlib.sha256(args.prices.read_bytes()).hexdigest())
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Hata: {exc}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
