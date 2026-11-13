"""Çevrimdışı örnek fiyatlar (CSV). Ağ bağlantısı kullanmaz."""

from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterator

SAMPLE_CSV = Path(__file__).resolve().parent.parent / "data" / "sample_prices.csv"


def load_prices(path: str | Path = SAMPLE_CSV) -> list[tuple[datetime, dict[str, Decimal]]]:
    """CSV'yi zaman sırasına göre [(zaman, {sembol: fiyat})] listesine çevirir.

    Beklenen sütunlar: timestamp, symbol, close
    """
    by_time: dict[datetime, dict[str, Decimal]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ts = datetime.fromisoformat(row["timestamp"])
            price = Decimal(row["close"])
            if price <= 0:
                raise ValueError(f"Geçersiz fiyat: {row}")
            by_time.setdefault(ts, {})[row["symbol"]] = price
    return sorted(by_time.items())


def iter_prices(path: str | Path = SAMPLE_CSV) -> Iterator[tuple[datetime, dict[str, Decimal]]]:
    yield from load_prices(path)
