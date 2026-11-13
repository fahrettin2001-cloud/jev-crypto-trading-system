"""SENTETİK (uydurma) saatlik fiyat üretir — gerçek piyasa verisi DEĞİLDİR.

Backtest motorunu, gerçek Binance geçmiş verisine erişim açılana kadar
yeterince uzun bir seri üzerinde denemek için. Sabit tohumla üretildiği için
her çalıştırmada aynı dosya çıkar.

Çalıştırma: python -m examples.sentetik_veri
  → data/synthetic_prices.csv (timestamp,symbol,close)
  → data/synthetic_klines/{BTCUSDT,ETHUSDT}-1h-sentetik.csv (Binance kline
    biçiminde açılış/yüksek/düşük/kapanış ve USDT hacmi)

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

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "synthetic_prices.csv"
KLINES = DATA / "synthetic_klines"
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
HOURS = 24 * 90
SEED = 20261113

# (saatlik sürüklenme, saatlik oynaklık)
REGIMES = [(0.0006, 0.008), (-0.0006, 0.010), (0.0, 0.006)]


def generate(hours: int = HOURS, seed: int = SEED, substeps: int = 6):
    """Her saat `substeps` alt adımda yürür; açılış/yüksek/düşük/kapanış ve
    hacim bu alt adımlardan çıkar. Döndürür: {sembol: [(açılış_ms, o, h, l, c, hacim)]}"""
    rng = random.Random(seed)
    price = {"BTCUSDT": 60000.0, "ETHUSDT": 3000.0}
    scale = {"BTCUSDT": 1.0, "ETHUSDT": 1.2}
    base_volume = {"BTCUSDT": 40_000_000.0, "ETHUSDT": 15_000_000.0}
    regime = rng.randrange(len(REGIMES))
    out = {s: [] for s in price}
    for h in range(hours):
        if rng.random() < 1 / 120:  # ortalama 5 günde bir rejim değişimi
            regime = rng.randrange(len(REGIMES))
        drift, vol = REGIMES[regime]
        drift, vol = drift / substeps, vol / math.sqrt(substeps)
        path = {s: [price[s]] for s in price}
        for _ in range(substeps):
            z_btc = rng.gauss(0, 1)
            z_eth = 0.8 * z_btc + math.sqrt(1 - 0.8 ** 2) * rng.gauss(0, 1)
            for s, z in (("BTCUSDT", z_btc), ("ETHUSDT", z_eth)):
                v = vol * scale[s]
                price[s] *= math.exp(drift * scale[s] - v ** 2 / 2 + v * z)
                path[s].append(price[s])
        open_ms = int((START + timedelta(hours=h)).timestamp() * 1000)
        for s in price:
            o, c = path[s][0], path[s][-1]
            hi, lo = max(path[s]), min(path[s])
            volume = base_volume[s] * rng.uniform(0.5, 1.5) * (1 + 20 * abs(c / o - 1))
            out[s].append((open_ms, round(o, 2), round(hi, 2), round(lo, 2), round(c, 2),
                           round(volume, 2)))
    return out


def main() -> None:
    data = generate()
    # Bar zamanı = kapanış zamanı (açılış + 1 saat)
    simple = sorted((datetime.fromtimestamp(r[0] / 1000 + 3600, timezone.utc).isoformat(), s,
                     f"{r[4]:.2f}") for s, rows in data.items() for r in rows)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["timestamp", "symbol", "close"])
        w.writerows(simple)
    KLINES.mkdir(exist_ok=True)
    for s, rows in data.items():
        path = KLINES / f"{s}-1h-sentetik.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            for open_ms, o, hi, lo, c, qv in rows:
                close_ms = open_ms + 3_600_000 - 1
                w.writerow([open_ms, f"{o:.2f}", f"{hi:.2f}", f"{lo:.2f}", f"{c:.2f}",
                            f"{qv / c:.5f}", close_ms, f"{qv:.2f}", 0, 0, 0, 0])
        print(f"Yazıldı: {path} (SENTETİK)")
    print(f"Yazıldı: {OUT} (SENTETİK, {len(simple)} satır)")


if __name__ == "__main__":
    main()
