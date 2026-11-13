"""Geçmiş fiyatları backtest barlarına çevirme. Ağ bağlantısı kurmaz.

Desteklenen kaynaklar:
- Projenin basit CSV'si (`timestamp,symbol,close`) — `data/sample_prices.csv`
- Binance Global'in halka açık geçmiş veri dosyaları (data.binance.vision,
  ör. `BTCUSDT-1h-2026-10.csv`): başlıksız, 12 sütunlu kline satırları.
  Sütun 0 açılış zamanı (ms; 2025'ten itibaren spot dosyalarında µs),
  sütun 4 kapanış, sütun 6 kapanış zamanı. Bar zamanı = kapanış zamanı,
  böylece strateji barı kapanmadan o barın fiyatını görmez.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from .prices import load_prices
from .strategy import Bar

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _from_epoch(raw: str) -> datetime:
    value = int(raw)
    # 13 hane milisaniye, 16 hane mikrosaniye
    micros = value if value >= 10**15 else value * 1000
    return _EPOCH + timedelta(microseconds=micros)


def load_binance_kline_csv(path: str | Path, symbol: str) -> dict[datetime, Decimal]:
    """data.binance.vision kline CSV'sini {kapanış zamanı: kapanış fiyatı} olarak okur."""
    out: dict[datetime, Decimal] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row or not row[0].strip().isdigit():
                continue  # olası başlık satırı
            if len(row) < 7:
                raise ValueError(f"{path}: beklenmeyen kline satırı: {row}")
            close = Decimal(row[4])
            if not close.is_finite() or close <= 0:
                raise ValueError(f"{path}: geçersiz kapanış fiyatı: {row}")
            # close_time ...999 ms ile biter; bir sonraki tam zamana yuvarla
            close_time = _from_epoch(row[6]) + timedelta(microseconds=1000 if int(row[6]) < 10**15 else 1)
            out[close_time.replace(microsecond=0)] = close
    if not out:
        raise ValueError(f"{path}: kline satırı bulunamadı")
    return out


def bars_from_series(series: dict[str, dict[datetime, Decimal]]) -> list[Bar]:
    """{sembol: {zaman: fiyat}} → zaman sıralı Bar listesi.

    Bir sembolün o zamanda verisi yoksa o barda yer almaz; motor son bilinen
    fiyatı değerleme için taşır ama o sembolde işlem yaptırmaz.
    """
    times: dict[datetime, dict[str, Decimal]] = {}
    for symbol, points in series.items():
        for ts, price in points.items():
            times.setdefault(ts, {})[symbol] = price
    return [Bar(ts, prices) for ts, prices in sorted(times.items())]


def bars_from_simple_csv(path: str | Path) -> list[Bar]:
    return [Bar(ts, prices) for ts, prices in load_prices(path)]


def load_bars(paths: Iterable[str | Path], *, kline_symbols: Iterable[str] | None = None) -> list[Bar]:
    """Basit CSV ya da Binance kline dosyalarından bar listesi.

    `kline_symbols` verilirse her dosya aynı sıradaki sembolün kline dosyası
    kabul edilir; aynı sembolün birden çok ayı ardışık verilebilir.
    """
    paths = [Path(p) for p in paths]
    if kline_symbols is None:
        if len(paths) != 1:
            raise ValueError("Basit CSV biçiminde tek dosya verin")
        return bars_from_simple_csv(paths[0])
    symbols = list(kline_symbols)
    if len(symbols) != len(paths):
        raise ValueError("Her kline dosyası için bir sembol verin")
    series: dict[str, dict[datetime, Decimal]] = {}
    for path, symbol in zip(paths, symbols):
        series.setdefault(symbol, {}).update(load_binance_kline_csv(path, symbol))
    return bars_from_series(series)
