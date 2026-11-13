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
MARKET, LIMIT = "MARKET", "LIMIT"


@dataclass(frozen=True)
class Bar:
    """Bir zaman adımı. `timestamp` barın KAPANIŞ zamanıdır.

    `prices` kapanış fiyatlarıdır (zorunlu). `opens`, `highs`, `lows` ve
    `quote_volumes` (karşı para cinsinden işlem hacmi) isteğe bağlıdır; yoksa
    açılış/yüksek/düşük kapanışa eşit kabul edilir, hacim bilinmiyor sayılır.
    """

    timestamp: datetime
    prices: Mapping[str, Decimal]
    opens: Mapping[str, Decimal] | None = None
    highs: Mapping[str, Decimal] | None = None
    lows: Mapping[str, Decimal] | None = None
    quote_volumes: Mapping[str, Decimal] | None = None

    def __post_init__(self) -> None:
        closes = _positive_prices(self.prices, "kapanış")
        object.__setattr__(self, "prices", MappingProxyType(closes))
        for name in ("opens", "highs", "lows"):
            raw = getattr(self, name)
            values = _positive_prices(raw or {}, name)
            if values.keys() - closes.keys():
                raise ValueError(f"{name}: kapanış fiyatı olmayan sembol")
            object.__setattr__(self, name, MappingProxyType(values))
        volumes = {s: D(v) for s, v in (self.quote_volumes or {}).items()}
        for s, v in volumes.items():
            if not v.is_finite() or v < 0:
                raise ValueError(f"{s} için geçersiz hacim: {v}")
        object.__setattr__(self, "quote_volumes", MappingProxyType(volumes))
        for s in closes:
            o, h, l, c = self.open(s), self.high(s), self.low(s), closes[s]
            if not (l <= min(o, c) and max(o, c) <= h):
                raise ValueError(f"{s}: tutarsız OHLC (açılış {o}, yüksek {h}, düşük {l}, kapanış {c})")

    def open(self, symbol: str) -> Decimal:
        return self.opens.get(symbol, self.prices[symbol])

    def high(self, symbol: str) -> Decimal:
        return self.highs.get(symbol, max(self.open(symbol), self.prices[symbol]))

    def low(self, symbol: str) -> Decimal:
        return self.lows.get(symbol, min(self.open(symbol), self.prices[symbol]))

    def quote_volume(self, symbol: str) -> Decimal | None:
        return self.quote_volumes.get(symbol)


def _positive_prices(raw: Mapping, label: str) -> dict[str, Decimal]:
    out = {s: D(p) for s, p in raw.items()}
    for s, p in out.items():
        if not p.is_finite() or p <= 0:
            raise ValueError(f"{s} için geçersiz {label} fiyatı: {p}")
    return out


@dataclass(frozen=True)
class OrderIntent:
    """Stratejinin işlem önerisi. Henüz işlem değildir.

    Alışta `quote_amount` (harcanacak USDT, komisyon dahil) ya da `quantity`;
    satışta `quantity` verilir. `quantity="ALL"` eldekinin tamamını satar.

    Emir türü: `MARKET` (varsayılan) ya da `LIMIT` (`limit_price` ve
    `good_for_bars` ile). Alışta isteğe bağlı `stop_loss` / `take_profit`
    mutlak fiyatları verilirse alış gerçekleştiğinde koruyucu çıkış kurulur.
    """

    symbol: str
    side: str
    quantity: Decimal | str | None = None
    quote_amount: Decimal | None = None
    reason: str = ""
    confidence: Decimal | None = None  # 0..1, yalnızca kayıt için
    order_type: str = MARKET
    limit_price: Decimal | None = None
    good_for_bars: int = 1
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None

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
        if self.order_type not in (MARKET, LIMIT):
            raise ValueError("order_type MARKET ya da LIMIT olmalı")
        if self.order_type == LIMIT:
            if self.limit_price is None:
                raise ValueError("Limit emirde limit_price zorunlu")
            if not isinstance(self.good_for_bars, int) or self.good_for_bars < 1:
                raise ValueError("good_for_bars en az 1 olan tam sayı olmalı")
        elif self.limit_price is not None:
            raise ValueError("limit_price yalnızca LIMIT emirde kullanılabilir")
        for name in ("limit_price", "stop_loss", "take_profit"):
            value = getattr(self, name)
            if value is None:
                continue
            v = D(value)
            if not v.is_finite() or v <= 0:
                raise ValueError(f"{name} pozitif olmalı")
            object.__setattr__(self, name, v)
        if (self.stop_loss is not None or self.take_profit is not None) and self.side != BUY:
            raise ValueError("stop_loss / take_profit yalnızca alışta verilebilir")
        if (self.stop_loss is not None and self.take_profit is not None
                and self.stop_loss >= self.take_profit):
            raise ValueError("stop_loss take_profit'ten küçük olmalı")


@dataclass(frozen=True)
class Hold:
    """İşlem yapmama kararı ("BEKLE"). İşlem üretmez; yalnızca karar günlüğüne
    yazılır, böylece modelin bekleme kararlarının isabeti de ölçülebilir."""

    symbol: str
    reason: str = ""
    confidence: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("Sembol boş olamaz")
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
    # Henüz gerçekleşmemiş emirler (bekleyen limit emirler). Strateji aynı
    # emri tekrar vermemek için bunlara bakmalı.
    open_orders: tuple["OrderIntent", ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "positions", MappingProxyType(dict(self.positions)))
        object.__setattr__(self, "open_orders", tuple(self.open_orders))

    def quantity(self, symbol: str) -> Decimal:
        return self.positions.get(symbol, Decimal("0"))


class Strategy(Protocol):
    name: str

    def on_bar(self, bar: Bar, view: PortfolioView) -> Iterable[OrderIntent | Hold]:
        """Bar kapandığında çağrılır; öneriler sonraki adımda değerlendirilir.
        `Hold` döndürmek işlem yapmaz, yalnızca karar günlüğüne yazılır."""
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

    def __init__(self, symbol: str, fast: int = 10, slow: int = 30, fraction="0.95",
                 stop_loss_pct=None, take_profit_pct=None, sizer=None):
        if not (isinstance(fast, int) and isinstance(slow, int)) or not 0 < fast < slow:
            raise ValueError("0 < fast < slow tam sayılar olmalı")
        self.symbol, self.fast, self.slow = symbol, fast, slow
        self.fraction = _fraction(fraction)
        # Alış anındaki kapanışa göre yüzde: 0.05 = %5 aşağıda zarar durdur
        self.stop_loss_pct = _fraction(stop_loss_pct) if stop_loss_pct is not None else None
        self.take_profit_pct = D(take_profit_pct) if take_profit_pct is not None else None
        if self.take_profit_pct is not None and (not self.take_profit_pct.is_finite()
                                                 or self.take_profit_pct <= 0):
            raise ValueError("take_profit_pct pozitif olmalı")
        extras = "".join(f",{k}{v * 100}%" for k, v in (("sl", self.stop_loss_pct),
                                                         ("tp", self.take_profit_pct)) if v)
        # sizer verilirse alış büyüklüğü sabit oran yerine oynaklığa göre belirlenir
        # (jev.sizing.VolatilityTargetSizer); `fraction` o durumda kullanılmaz.
        self.sizer = sizer
        if sizer is not None:
            extras += f",{sizer.describe()}"
        self.name = f"sma-kesisim({symbol},{fast}/{slow}{extras})"
        self._prices: deque[Decimal] = deque(maxlen=slow)
        self._prev_diff: Decimal | None = None

    def on_bar(self, bar, view):
        price = bar.prices.get(self.symbol)
        if price is None:
            return []
        self._prices.append(price)
        if self.sizer is not None:
            self.sizer.observe(self.symbol, price)
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
            if self.sizer is None:
                amount, sizing = view.cash * self.fraction, ""
            else:
                frac = self.sizer.fraction(self.symbol)
                if frac is None or frac <= 0:
                    return []  # oynaklık için yeterli geçmiş yok
                # Hedef: toplam varlığın frac kadarı; nakitten fazlası olamaz
                amount = min(view.equity * frac, view.cash)
                sizing = f"; oynaklığa göre varlığın %{frac * 100}"
                if amount <= 0:
                    return []
            return [OrderIntent(
                self.symbol, BUY, quote_amount=amount,
                reason=f"SMA{self.fast} SMA{self.slow}'u yukarı kesti{sizing}",
                stop_loss=price * (1 - self.stop_loss_pct) if self.stop_loss_pct else None,
                take_profit=price * (1 + self.take_profit_pct) if self.take_profit_pct else None)]
        if prev >= 0 > diff and held > 0:
            return [OrderIntent(self.symbol, SELL, quantity="ALL",
                                reason=f"SMA{self.fast} SMA{self.slow}'u aşağı kesti")]
        return []


def _fraction(value) -> Decimal:
    f = D(value)
    if not f.is_finite() or not 0 < f <= 1:
        raise ValueError("Oran 0 ile 1 arasında olmalı (0 hariç)")
    return f
