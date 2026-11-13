"""Sanal portföy: nakit, pozisyonlar, alım-satım ve kâr/zarar.

Gerçek borsaya hiçbir şekilde bağlanmaz. Fiyatlar dışarıdan verilir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Mapping

from .fees import D, FeeSchedule


class TradeError(ValueError):
    """Geçersiz veya karşılanamayan sanal işlem."""


@dataclass
class Position:
    quantity: Decimal = Decimal("0")
    avg_cost: Decimal = Decimal("0")  # birim başına, komisyon dahil


@dataclass(frozen=True)
class Trade:
    timestamp: datetime
    symbol: str
    side: str  # "BUY" veya "SELL"
    quantity: Decimal
    price: Decimal
    fee: Decimal
    realized_pnl: Decimal  # yalnızca satışlarda sıfırdan farklı


@dataclass
class Portfolio:
    cash: Decimal
    fees: FeeSchedule = field(default_factory=FeeSchedule)
    quote: str = "USDT"
    positions: dict[str, Position] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cash = D(self.cash)
        if self.cash < 0:
            raise ValueError("Başlangıç nakdi negatif olamaz")
        self.initial_cash = self.cash

    # --- işlemler -------------------------------------------------------

    def buy(self, symbol: str, quantity, price, *, taker: bool = True,
            timestamp: datetime | None = None) -> Trade:
        quantity, price = self._validate(quantity, price)
        notional = quantity * price
        fee = self.fees.fee(notional, taker)
        total = notional + fee
        if total > self.cash:
            raise TradeError(
                f"Yetersiz nakit: gereken {total} {self.quote}, mevcut {self.cash}")

        pos = self.positions.setdefault(symbol, Position())
        new_qty = pos.quantity + quantity
        # Komisyon maliyete eklenir; böylece satıştaki kâr gerçek getiriyi gösterir.
        pos.avg_cost = (pos.avg_cost * pos.quantity + total) / new_qty
        pos.quantity = new_qty
        self.cash -= total
        return self._record(timestamp, symbol, "BUY", quantity, price, fee, Decimal("0"))

    def sell(self, symbol: str, quantity, price, *, taker: bool = True,
             timestamp: datetime | None = None) -> Trade:
        quantity, price = self._validate(quantity, price)
        pos = self.positions.get(symbol)
        held = pos.quantity if pos else Decimal("0")
        if quantity > held:
            raise TradeError(f"Yetersiz {symbol}: satılmak istenen {quantity}, eldeki {held}")

        notional = quantity * price
        fee = self.fees.fee(notional, taker)
        proceeds = notional - fee
        realized = proceeds - pos.avg_cost * quantity

        pos.quantity -= quantity
        if pos.quantity == 0:
            del self.positions[symbol]
        self.cash += proceeds
        return self._record(timestamp, symbol, "SELL", quantity, price, fee, realized)

    # --- raporlama ------------------------------------------------------

    def market_value(self, prices: Mapping[str, Decimal]) -> Decimal:
        """Pozisyonların güncel değeri (nakit hariç)."""
        total = Decimal("0")
        for symbol, pos in self.positions.items():
            if symbol not in prices:
                raise KeyError(f"{symbol} için fiyat yok")
            total += pos.quantity * D(prices[symbol])
        return total

    def equity(self, prices: Mapping[str, Decimal]) -> Decimal:
        return self.cash + self.market_value(prices)

    def unrealized_pnl(self, prices: Mapping[str, Decimal]) -> Decimal:
        return sum(
            (pos.quantity * (D(prices[s]) - pos.avg_cost) for s, pos in self.positions.items()),
            Decimal("0"),
        )

    @property
    def realized_pnl(self) -> Decimal:
        return sum((t.realized_pnl for t in self.trades), Decimal("0"))

    @property
    def total_fees(self) -> Decimal:
        return sum((t.fee for t in self.trades), Decimal("0"))

    # --- yardımcılar ----------------------------------------------------

    @staticmethod
    def _validate(quantity, price) -> tuple[Decimal, Decimal]:
        quantity, price = D(quantity), D(price)
        if quantity <= 0:
            raise TradeError("Miktar pozitif olmalı")
        if price <= 0:
            raise TradeError("Fiyat pozitif olmalı")
        return quantity, price

    def _record(self, timestamp, symbol, side, quantity, price, fee, realized) -> Trade:
        trade = Trade(timestamp or datetime.now(timezone.utc), symbol, side,
                      quantity, price, fee, realized)
        self.trades.append(trade)
        return trade
