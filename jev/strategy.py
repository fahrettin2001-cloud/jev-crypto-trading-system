"""Strateji arayüzü: kim, neye göre işlem önerir?

Akış: strateji (ileride Jev / güçlü model) her bar için `OrderIntent` önerir
→ işlem kuralları ve risk kontrolü onaylar ya da reddeder → sanal portföyde
işlem yapılır. Strateji portföyü doğrudan değiştiremez; yalnızca salt okunur
bir `PortfolioView` görür ve yalnızca o ana kadarki fiyatları bilir.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Iterable, Mapping, Protocol

from .fees import D

BUY, SELL = "BUY", "SELL"


@dataclass(frozen=True)
class Bar:
    """Bir zaman adımındaki kapanış fiyatları."""

    timestamp: datetime
    prices: Mapping[str, Decimal]

    def __post_init__(self) -> None:
        prices = {s: D(p) for s, p in self.prices.items()}
        for s, p in prices.items():
            if not p.is_finite() or p <= 0:
                raise ValueError(f"{s} için geçersiz fiyat: {p}")
        object.__setattr__(self, "prices", MappingProxyType(prices))


@dataclass(frozen=True)
class OrderIntent:
    """Stratejinin işlem önerisi. Henüz işlem değildir.

    Alışta `quote_amount` (harcanacak USDT, komisyon dahil) ya da `quantity`;
    satışta `quantity` verilir. `quantity="ALL"` eldekinin tamamını satar.
    """

    symbol: str
    side: str
    quantity: Decimal | str | None = None
    quote_amount: Decimal | None = None
    reason: str = ""
    confidence: Decimal | None = None  # 0..1, yalnızca kayıt için

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("Sembol boş olamaz")
        if self.side not in (BUY, SELL):
            raise ValueError("side BUY ya da SELL olmalı")
        if (self.quantity is None) == (self.quote_amount is None):
            raise ValueError("quantity ya da quote_amount'tan tam olarak biri verilmeli")
        if self.quantity == "ALL":
            if self.side != SELL:
                raise ValueError('quantity="ALL" yalnızca satışta kullanılabilir')
        elif self.quantity is not None:
            q = D(self.quantity)
            if not q.is_finite() or q <= 0:
                raise ValueError("Miktar pozitif olmalı")
            object.__setattr__(self, "quantity", q)
        if self.quote_amount is not None:
            if self.side != BUY:
                raise ValueError("quote_amount yalnızca alışta kullanılabilir")
            a = D(self.quote_amount)
            if not a.is_finite() or a <= 0:
                raise ValueError("Tutar pozitif olmalı")
            object.__setattr__(self, "quote_amount", a)
        if self.confidence is not None:
            c = D(self.confidence)
            if not c.is_finite() or not 0 <= c <= 1:
                raise ValueError("confidence 0 ile 1 arasında olmalı")
            object.__setattr__(self, "confidence", c)


@dataclass(frozen=True)
class PortfolioView:
    """Stratejiye gösterilen salt okunur portföy özeti."""

    cash: Decimal
    positions: Mapping[str, Decimal] = field(default_factory=dict)
    equity: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        object.__setattr__(self, "positions", MappingProxyType(dict(self.positions)))

    def quantity(self, symbol: str) -> Decimal:
        return self.positions.get(symbol, Decimal("0"))


class Strategy(Protocol):
    name: str

    def on_bar(self, bar: Bar, view: PortfolioView) -> Iterable[OrderIntent]:
        """Bar kapandığında çağrılır; öneriler sonraki adımda değerlendirilir."""
        ...


# --- örnek stratejiler --------------------------------------------------------


class BuyAndHold:
    """İlk barda nakdin belirli oranıyla alır, sonra bekler. Kıyas için."""

    def __init__(self, symbol: str, fraction="1"):
        self.symbol = symbol
        self.fraction = _fraction(fraction)
        self.name = f"al-tut({symbol})"
        self._done = False

    def on_bar(self, bar, view):
        if self._done or self.symbol not in bar.prices:
            return []
        self._done = True
        return [OrderIntent(self.symbol, BUY, quote_amount=view.cash * self.fraction,
                            reason="al-tut: ilk bar")]


class SmaCross:
    """Hareketli ortalama kesişimi: hızlı ortalama yavaşı yukarı keserse al,
    aşağı keserse tamamını sat. Basit, bilinen bir örnek; kârlılık iddiası yoktur."""

    def __init__(self, symbol: str, fast: int = 10, slow: int = 30, fraction="0.95"):
        if not (isinstance(fast, int) and isinstance(slow, int)) or not 0 < fast < slow:
            raise ValueError("0 < fast < slow tam sayılar olmalı")
        self.symbol, self.fast, self.slow = symbol, fast, slow
        self.fraction = _fraction(fraction)
        self.name = f"sma-kesisim({symbol},{fast}/{slow})"
        self._prices: deque[Decimal] = deque(maxlen=slow)
        self._prev_diff: Decimal | None = None

    def on_bar(self, bar, view):
        price = bar.prices.get(self.symbol)
        if price is None:
            return []
        self._prices.append(price)
        if len(self._prices) < self.slow:
            return []
        prices = list(self._prices)
        fast = sum(prices[-self.fast:], Decimal("0")) / self.fast
        slow = sum(prices, Decimal("0")) / self.slow
        diff = fast - slow
        prev, self._prev_diff = self._prev_diff, diff
        if prev is None:
            return []
        held = view.quantity(self.symbol)
        if prev <= 0 < diff and held == 0:
            return [OrderIntent(self.symbol, BUY, quote_amount=view.cash * self.fraction,
                                reason=f"SMA{self.fast} SMA{self.slow}'u yukarı kesti")]
        if prev >= 0 > diff and held > 0:
            return [OrderIntent(self.symbol, SELL, quantity="ALL",
                                reason=f"SMA{self.fast} SMA{self.slow}'u aşağı kesti")]
        return []


def _fraction(value) -> Decimal:
    f = D(value)
    if not f.is_finite() or not 0 < f <= 1:
        raise ValueError("Oran 0 ile 1 arasında olmalı (0 hariç)")
    return f
