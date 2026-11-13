"""Binance Global spot işlem kuralları (exchangeInfo filtreleri).

Gerçek Binance, kurallara uymayan emri reddeder: miktar LOT_SIZE adımının
katı olmalı, fiyat PRICE_FILTER adımının katı olmalı, işlem tutarı NOTIONAL
sınırları içinde kalmalı. Sanal işlemde de aynı kuralları uygulamazsak
sonuçlar gerçekte yapılamayacak işlemlere dayanır.

`ExchangeRules.from_exchange_info` doğrudan `GET /api/v3/exchangeInfo`
cevabını okur; ağ bağlantısı kurmaz. Cevap dosyaya kaydedilip `load` ile
kullanılır.

Bilinen sadeleştirme: Binance piyasa emirlerinde NOTIONAL kontrolünü son
`avgPriceMins` dakikanın ortalama fiyatıyla yapar; burada işlem fiyatı
kullanılır.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_UP, Decimal
from pathlib import Path
from typing import Mapping

from .fees import D
from .portfolio import TradeError

SAMPLE_EXCHANGE_INFO = (Path(__file__).resolve().parent.parent
                        / "data" / "exchange_info_sample.json")


class ExchangeRuleError(TradeError):
    """Emir Binance işlem kurallarından geçemedi."""


def _floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step == 0:
        return value
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def _is_multiple(value: Decimal, base: Decimal, step: Decimal) -> bool:
    if step == 0:
        return True
    return ((value - base) % step) == 0


@dataclass(frozen=True)
class SymbolRules:
    symbol: str
    base_asset: str
    quote_asset: str
    status: str = "TRADING"
    # PRICE_FILTER (0 = kural kapalı, Binance ile aynı)
    min_price: Decimal = Decimal("0")
    max_price: Decimal = Decimal("0")
    tick_size: Decimal = Decimal("0")
    # LOT_SIZE
    min_qty: Decimal = Decimal("0")
    max_qty: Decimal = Decimal("0")
    step_size: Decimal = Decimal("0")
    # MARKET_LOT_SIZE (yoksa LOT_SIZE yeterli)
    market_min_qty: Decimal = Decimal("0")
    market_max_qty: Decimal = Decimal("0")
    market_step_size: Decimal = Decimal("0")
    # NOTIONAL / MIN_NOTIONAL
    min_notional: Decimal = Decimal("0")
    max_notional: Decimal = Decimal("0")
    apply_min_to_market: bool = True
    apply_max_to_market: bool = False

    def __post_init__(self) -> None:
        for name in ("min_price", "max_price", "tick_size", "min_qty", "max_qty",
                     "step_size", "market_min_qty", "market_max_qty",
                     "market_step_size", "min_notional", "max_notional"):
            value = D(getattr(self, name))
            if not value.is_finite() or value < 0:
                raise ValueError(f"{self.symbol}: geçersiz {name}: {value}")
            object.__setattr__(self, name, value)

    # --- yuvarlama --------------------------------------------------------

    def floor_quantity(self, quantity, *, market: bool = True) -> Decimal:
        """Miktarı izin verilen adıma aşağı yuvarlar (asla yukarı değil)."""
        quantity = D(quantity)
        step = self.step_size
        if market and self.market_step_size > step:
            step = self.market_step_size
        base = self.min_qty
        if step == 0:
            return quantity
        # Binance kuralı: (quantity - minQty) % stepSize == 0
        return base + _floor_to_step(quantity - base, step) if quantity >= base else Decimal("0")

    def round_price(self, price, *, up: bool = False) -> Decimal:
        """Fiyatı tick adımına yuvarlar; alış limitleri için aşağı, satış için yukarı."""
        price = D(price)
        if self.tick_size == 0:
            return price
        steps = ((price - self.min_price) / self.tick_size).to_integral_value(
            rounding=ROUND_UP if up else ROUND_DOWN)
        return self.min_price + steps * self.tick_size

    # --- doğrulama --------------------------------------------------------

    def check(self, quantity, price, *, market: bool = True,
              check_price_filter: bool | None = None) -> None:
        """Emri Binance filtrelerine göre doğrular; uymazsa ExchangeRuleError.

        Piyasa emrinde fiyat emirde yer almadığı için PRICE_FILTER varsayılan
        olarak yalnızca limit emirlerde (market=False) uygulanır.
        """
        quantity, price = D(quantity), D(price)
        if self.status != "TRADING":
            raise ExchangeRuleError(f"{self.symbol} işleme açık değil (durum: {self.status})")
        if quantity <= 0 or price <= 0:
            raise ExchangeRuleError("Miktar ve fiyat pozitif olmalı")

        if check_price_filter if check_price_filter is not None else not market:
            self.check_price(price)

        lots = [("LOT_SIZE", self.min_qty, self.max_qty, self.step_size)]
        if market and (self.market_min_qty or self.market_max_qty or self.market_step_size):
            lots.append(("MARKET_LOT_SIZE", self.market_min_qty, self.market_max_qty,
                         self.market_step_size))
        for name, lo, hi, step in lots:
            if lo and quantity < lo:
                raise ExchangeRuleError(f"{name}: miktar {quantity} < asgari {lo}")
            if hi and quantity > hi:
                raise ExchangeRuleError(f"{name}: miktar {quantity} > azami {hi}")
            if not _is_multiple(quantity, lo, step):
                raise ExchangeRuleError(f"{name}: miktar {quantity} adım {step} katı değil")

        notional = quantity * price
        if self.min_notional and (self.apply_min_to_market or not market) \
                and notional < self.min_notional:
            raise ExchangeRuleError(f"NOTIONAL: tutar {notional} < asgari {self.min_notional}")
        if self.max_notional and (self.apply_max_to_market or not market) \
                and notional > self.max_notional:
            raise ExchangeRuleError(f"NOTIONAL: tutar {notional} > azami {self.max_notional}")

    def check_price(self, price) -> None:
        """Limit fiyatını PRICE_FILTER'a göre doğrular."""
        price = D(price)
        if self.min_price and price < self.min_price:
            raise ExchangeRuleError(f"PRICE_FILTER: fiyat {price} < asgari {self.min_price}")
        if self.max_price and price > self.max_price:
            raise ExchangeRuleError(f"PRICE_FILTER: fiyat {price} > azami {self.max_price}")
        if not _is_multiple(price, self.min_price, self.tick_size):
            raise ExchangeRuleError(f"PRICE_FILTER: fiyat {price} tick {self.tick_size} katı değil")

    # --- exchangeInfo ayrıştırma ------------------------------------------

    @classmethod
    def from_symbol_info(cls, info: Mapping) -> "SymbolRules":
        kwargs = {
            "symbol": info["symbol"],
            "base_asset": info["baseAsset"],
            "quote_asset": info["quoteAsset"],
            "status": info.get("status", "TRADING"),
        }
        for f in info.get("filters", []):
            kind = f.get("filterType")
            if kind == "PRICE_FILTER":
                kwargs.update(min_price=f["minPrice"], max_price=f["maxPrice"],
                              tick_size=f["tickSize"])
            elif kind == "LOT_SIZE":
                kwargs.update(min_qty=f["minQty"], max_qty=f["maxQty"], step_size=f["stepSize"])
            elif kind == "MARKET_LOT_SIZE":
                kwargs.update(market_min_qty=f["minQty"], market_max_qty=f["maxQty"],
                              market_step_size=f["stepSize"])
            elif kind == "NOTIONAL":
                kwargs.update(min_notional=f.get("minNotional", "0"),
                              max_notional=f.get("maxNotional", "0"),
                              apply_min_to_market=bool(f.get("applyMinToMarket", True)),
                              apply_max_to_market=bool(f.get("applyMaxToMarket", False)))
            elif kind == "MIN_NOTIONAL":  # eski biçim
                kwargs.update(min_notional=f["minNotional"],
                              apply_min_to_market=bool(f.get("applyToMarket", True)))
            # Diğer filtreler (PERCENT_PRICE_BY_SIDE, ICEBERG_PARTS, MAX_NUM_ORDERS...)
            # sanal piyasa emri için şimdilik uygulanmaz.
        return cls(**kwargs)


class ExchangeRules:
    """Sembol -> SymbolRules eşlemesi."""

    def __init__(self, rules: Mapping[str, SymbolRules]):
        self._rules = dict(rules)

    @classmethod
    def from_exchange_info(cls, data: Mapping) -> "ExchangeRules":
        symbols = data.get("symbols")
        if not isinstance(symbols, list) or not symbols:
            raise ValueError("exchangeInfo cevabında 'symbols' listesi yok")
        return cls({s["symbol"]: SymbolRules.from_symbol_info(s) for s in symbols})

    @classmethod
    def load(cls, path: str | Path = SAMPLE_EXCHANGE_INFO) -> "ExchangeRules":
        with open(path, encoding="utf-8") as f:
            return cls.from_exchange_info(json.load(f))

    def __getitem__(self, symbol: str) -> SymbolRules:
        try:
            return self._rules[symbol]
        except KeyError:
            raise ExchangeRuleError(f"{symbol} için işlem kuralı yok") from None

    def __contains__(self, symbol: str) -> bool:
        return symbol in self._rules

    def symbols(self) -> list[str]:
        return sorted(self._rules)
