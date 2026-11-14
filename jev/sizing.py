"""Oynaklığa göre pozisyon büyüklüğü (volatility targeting).

Fikir: Piyasa sakinken daha büyük, çalkantılıyken daha küçük pozisyon al;
böylece portföyün günlük dalgalanması kabaca sabit kalır.

    hedef_oran = hedef_günlük_oynaklık / gerçekleşen_günlük_oynaklık

Gerçekleşen oynaklık, son `window` barın logaritmik getirilerinin standart
sapması × √(günlük bar sayısı). Oran `[0, max_fraction]` aralığına kırpılır.
Yeterli geçmiş yoksa oran bilinmez (`None`) ve strateji alım yapmamalıdır.

Bu bir risk aracıdır, getiri tahmini değildir. Oynaklık geçmişe bakar;
ani şoklarda gecikmeli tepki verir. Risk limitleri (`RiskLimits`) ayrıca
ve her durumda uygulanır.
"""

from __future__ import annotations

import math
from collections import deque
from decimal import ROUND_DOWN, Decimal

from .fees import D

_FOUR = Decimal("0.0001")


def realized_volatility(closes, bars_per_day: int) -> float | None:
    """Kapanış fiyatlarından günlüğe çevrilmiş oynaklık; en az 3 fiyat gerekir."""
    values = [float(c) for c in closes]
    if len(values) < 3:
        return None
    if any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError("Fiyatlar pozitif ve sonlu olmalı")
    rets = [math.log(b / a) for a, b in zip(values, values[1:])]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(bars_per_day)


class VolatilityTargetSizer:
    """Sembol başına kapanışları izler ve hedef pozisyon oranını verir.

    target_daily_vol: hedef günlük oynaklık (0.02 = %2)
    window: oynaklık için bakılacak bar sayısı (ör. 1 saatlik veride 72 = 3 gün)
    bars_per_day: günlük bar sayısı (1s → 24, 4s → 6, 1g → 1)
    max_fraction: bir pozisyonun varlığa oranı için üst sınır
    """

    def __init__(self, target_daily_vol="0.02", window: int = 72, bars_per_day: int = 24,
                 max_fraction="0.95"):
        self.target = D(target_daily_vol)
        if not self.target.is_finite() or self.target <= 0:
            raise ValueError("Hedef oynaklık pozitif olmalı")
        if not isinstance(window, int) or window < 3:
            raise ValueError("window en az 3 olan tam sayı olmalı")
        if not isinstance(bars_per_day, int) or bars_per_day < 1:
            raise ValueError("bars_per_day pozitif tam sayı olmalı")
        self.max_fraction = D(max_fraction)
        if not self.max_fraction.is_finite() or not 0 < self.max_fraction <= 1:
            raise ValueError("max_fraction 0 ile 1 arasında olmalı (0 hariç)")
        self.window, self.bars_per_day = window, bars_per_day
        self._closes: dict[str, deque] = {}

    def observe(self, symbol: str, close) -> None:
        self._closes.setdefault(symbol, deque(maxlen=self.window + 1)).append(D(close))

    def volatility(self, symbol: str) -> float | None:
        closes = self._closes.get(symbol)
        if closes is None or len(closes) < self.window + 1:
            return None
        return realized_volatility(closes, self.bars_per_day)

    def fraction(self, symbol: str) -> Decimal | None:
        """Varlığın ne kadarı bu sembole ayrılmalı; geçmiş yetersizse None."""
        vol = self.volatility(symbol)
        if vol is None:
            return None
        if vol == 0:
            return self.max_fraction
        raw = self.target / D(vol)
        return min(raw, self.max_fraction).quantize(_FOUR, rounding=ROUND_DOWN)

    def describe(self) -> str:
        return f"oynaklık-hedefi %{self.target * 100}/gün, {self.window} bar"
