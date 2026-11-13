"""İşlem açmadan geçmiş fiyatlar üzerinde olasılık tahminlerini ölçer.

Tahminciye yalnızca o ana kadarki barlar verilir. Tahminin anlamı sabittir:
``horizon`` bar sonra kapanış, tahmin anındaki kapanıştan yüksek mi?
Bu modül API çağrısı veya emir üretimi yapmaz.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Callable, Sequence

from .fees import D
from .strategy import Bar


@dataclass(frozen=True)
class ShadowResult:
    timestamp: datetime
    symbol: str
    price: Decimal
    horizon: int
    probability: Decimal
    outcome_time: datetime | None
    outcome_price: Decimal | None
    increased: bool | None


def replay(bars: Sequence[Bar], symbol: str, horizon: int,
           predict: Callable[[tuple[Bar, ...], str, int], Decimal]) -> list[ShadowResult]:
    """Tahminleri çevrimdışı oynat; eksik gelecek sonucu ``None`` olarak bırak."""
    bars = tuple(bars)
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("Sembol boş olamaz")
    if type(horizon) is not int or horizon < 1:
        raise ValueError("Tahmin ufku pozitif tam sayı olmalı")
    previous = None
    for bar in bars:
        if bar.timestamp.utcoffset() is None:
            raise ValueError("Bar zamanı saat dilimi içermeli")
        if previous is not None and bar.timestamp <= previous:
            raise ValueError("Bar zamanları kesinlikle artmalı")
        if symbol not in bar.prices:
            raise ValueError("Her barda istenen sembol bulunmalı")
        previous = bar.timestamp

    predictions = []
    for i, bar in enumerate(bars):
        p = D(predict(bars[:i + 1], symbol, horizon))
        if not p.is_finite() or not 0 <= p <= 1:
            raise ValueError("Tahmin olasılığı 0 ile 1 arasında sonlu olmalı")
        # Yalnızca tahmin tamamlandıktan sonra değerlendirme sonucu okunur.
        future = bars[i + horizon] if i + horizon < len(bars) else None
        future_price = future.prices[symbol] if future else None
        predictions.append(ShadowResult(
            bar.timestamp, symbol, bar.prices[symbol], horizon, p,
            future.timestamp if future else None, future_price,
            future_price > bar.prices[symbol] if future else None,
        ))
    return predictions


def brier_score(results: Sequence[ShadowResult]) -> Decimal | None:
    """Yalnızca sonucu bilinen tahminler; düşük olması daha iyidir."""
    resolved = [r for r in results if r.increased is not None]
    if not resolved:
        return None
    return sum(((r.probability - int(r.increased)) ** 2 for r in resolved), Decimal(0)) / len(resolved)
