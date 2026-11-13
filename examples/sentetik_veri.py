"""SENTETİK (uydurma) saatlik fiyat üretir — gerçek piyasa verisi DEĞİLDİR.

Backtest motorunu, gerçek Binance geçmiş verisine erişim açılana kadar
yeterince uzun bir seri üzerinde denemek için. Sabit tohumla üretildiği için
her çalıştırmada aynı dosya çıkar.

Çalıştırma: python -m examples.sentetik_veri  → data/synthetic_prices.csv

Model: rejim değiştiren (yükseliş / düşüş / yatay) geometrik rastgele yürüyüş;
ETH, BTC hareketiyle kısmen bağıntılı. Gerçek fiyat davranışını (kalın kuyruklar,
haber şokları, likidite) temsil ettiği iddia edilmez.
"""

from __future__ import annotations

import csv
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "synthetic_prices.csv"
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
HOURS = 24 * 90
SEED = 20261113

# (saatlik sürüklenme, saatlik oynaklık)
REGIMES = [(0.0006, 0.008), (-0.0006, 0.010), (0.0, 0.006)]


def generate(hours: int = HOURS, seed: int = SEED):
    rng = random.Random(seed)
    btc, eth = 60000.0, 3000.0
    regime = rng.randrange(len(REGIMES))
    rows = []
    for h in range(hours):
        if rng.random() < 1 / 120:  # ortalama 5 günde bir rejim değişimi
            regime = rng.randrange(len(REGIMES))
        drift, vol = REGIMES[regime]
        z_btc = rng.gauss(0, 1)
        z_eth = 0.8 * z_btc + math.sqrt(1 - 0.8 ** 2) * rng.gauss(0, 1)
        btc *= math.exp(drift - vol ** 2 / 2 + vol * z_btc)
        eth *= math.exp(drift * 1.2 - (vol * 1.2) ** 2 / 2 + vol * 1.2 * z_eth)
        ts = (START + timedelta(hours=h + 1)).isoformat()
        rows.append((ts, "BTCUSDT", f"{btc:.2f}"))
        rows.append((ts, "ETHUSDT", f"{eth:.2f}"))
    return rows


def main() -> None:
    rows = generate()
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "symbol", "close"])
        w.writerows(rows)
    print(f"{len(rows)} satır yazıldı: {OUT} (SENTETİK veri)")


if __name__ == "__main__":
    main()
