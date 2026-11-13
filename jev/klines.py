"""Geçmiş fiyatları backtest barlarına çevirme. Ağ bağlantısı kurmaz.

Desteklenen kaynaklar:
- Projenin basit CSV'si (`timestamp,symbol,close`) — `data/sample_prices.csv`
- Binance Global'in halka açık geçmiş veri dosyaları (data.binance.vision,
  ör. `BTCUSDT-1h-2026-10.csv`): başlıksız, 12 sütunlu kline satırları.
  Sütun 0 açılış zamanı (ms; 2025'ten itibaren spot dosyalarında µs),
  sütun 1-4 açılış/yüksek/düşük/kapanış, sütun 6 kapanış zamanı, sütun 7
  karşı para (USDT) hacmi. Bar zamanı = kapanış zamanı, böylece strateji barı
  kapanmadan o barın fiyatını görmez.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Union

from .prices import load_prices
from .strategy import Bar

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _from_epoch(raw: str) -> datetime:
    value = int(raw)
    # 13 hane milisaniye, 16 hane mikrosaniye
    micros = value if value >= 10**15 else value * 1000
    return _EPOCH + timedelta(microseconds=micros)


@dataclass(frozen=True)
class Candle:
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    quote_volume: Decimal | None = None


def load_binance_klines(path: str | Path) -> dict[datetime, Candle]:
    """data.binance.vision kline CSV'sini {kapanış zamanı: Candle} olarak okur."""
    out: dict[datetime, Candle] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row or not row[0].strip().isdigit():
                continue  # olası başlık satırı
            if len(row) < 7:
                raise ValueError(f"{path}: beklenmeyen kline satırı: {row}")
            o, h, l, c = (Decimal(x) for x in row[1:5])
            if any(not v.is_finite() or v <= 0 for v in (o, h, l, c)):
                raise ValueError(f"{path}: geçersiz fiyat: {row}")
            if not (l <= min(o, c) and max(o, c) <= h):
                raise ValueError(f"{path}: tutarsız OHLC: {row}")
            volume = Decimal(row[7]) if len(row) > 7 and row[7].strip() else None
            raw_close = int(row[6])
            # close_time ...999 ile biter; bir sonraki tam zamana yuvarla
            close_time = _from_epoch(row[6]) + timedelta(microseconds=1000 if raw_close < 10**15 else 1)
            out[close_time.replace(microsecond=0)] = Candle(o, h, l, c, volume)
    if not out:
        raise ValueError(f"{path}: kline satırı bulunamadı")
    return out


def load_binance_kline_csv(path: str | Path, symbol: str | None = None) -> dict[datetime, Decimal]:
    """Yalnızca kapanış fiyatları: {kapanış zamanı: kapanış}."""
    return {ts: c.close for ts, c in load_binance_klines(path).items()}


def bars_from_series(series: dict[str, dict[datetime, Union[Decimal, Candle]]]) -> list[Bar]:
    """{sembol: {zaman: fiyat ya da Candle}} → zaman sıralı Bar listesi.

    Bir sembolün o zamanda verisi yoksa o barda yer almaz; motor son bilinen
    fiyatı değerleme için taşır ama o sembolde işlem yaptırmaz.
    """
    times: dict[datetime, dict[str, Union[Decimal, Candle]]] = {}
    for symbol, points in series.items():
        for ts, value in points.items():
            times.setdefault(ts, {})[symbol] = value
    bars = []
    for ts, values in sorted(times.items()):
        closes, opens, highs, lows, volumes = {}, {}, {}, {}, {}
        for symbol, v in values.items():
            if isinstance(v, Candle):
                closes[symbol], opens[symbol] = v.close, v.open
                highs[symbol], lows[symbol] = v.high, v.low
                if v.quote_volume is not None:
                    volumes[symbol] = v.quote_volume
            else:
                closes[symbol] = v
        bars.append(Bar(ts, closes, opens, highs, lows, volumes))
    return bars


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
    series: dict[str, dict[datetime, Candle]] = {}
    for path, symbol in zip(paths, symbols):
        series.setdefault(symbol, {}).update(load_binance_klines(path))
    return bars_from_series(series)
