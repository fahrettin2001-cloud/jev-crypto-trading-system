"""Sanal portföy: nakit, pozisyonlar, alım-satım ve kâr/zarar.

Gerçek borsaya hiçbir şekilde bağlanmaz. Fiyatlar dışarıdan verilir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import sqlite3
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
        if not self.cash.is_finite() or self.cash < 0:
            raise ValueError("Başlangıç nakdi sonlu ve negatif olmayan bir değer olmalı")
        self.initial_cash = self.cash
        self._db = None

    # --- işlemler -------------------------------------------------------

    def buy(self, symbol: str, quantity, price, *, taker: bool = True,
            timestamp: datetime | None = None) -> Trade:
        self._ensure_open()
        if self._db is not None:
            return self._persistent_trade("buy", symbol, quantity, price, taker=taker, timestamp=timestamp)
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
        self._ensure_open()
        if self._db is not None:
            return self._persistent_trade("sell", symbol, quantity, price, taker=taker, timestamp=timestamp)
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

    @classmethod
    def create(cls, path, cash, fees=None, quote="USDT"):
        """Yeni kalıcı portföy oluştur; mevcut portföyü sıfırlama."""
        portfolio = cls(cash=cash, fees=fees or FeeSchedule(), quote=quote)
        db = sqlite3.connect(path, timeout=10, isolation_level=None)
        try:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS portfolio_meta (id INTEGER PRIMARY KEY CHECK(id=1), initial_cash TEXT NOT NULL, cash TEXT NOT NULL, quote TEXT NOT NULL, maker_rate TEXT NOT NULL, taker_rate TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS positions (symbol TEXT PRIMARY KEY, quantity TEXT NOT NULL, avg_cost TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL, quantity TEXT NOT NULL, price TEXT NOT NULL, fee TEXT NOT NULL, realized_pnl TEXT NOT NULL)")
            if db.execute("SELECT 1 FROM portfolio_meta WHERE id=1").fetchone():
                raise TradeError("Portföy zaten mevcut")
            db.execute("INSERT INTO portfolio_meta VALUES (1, ?, ?, ?, ?, ?)", (str(portfolio.cash), str(portfolio.cash), quote, str(portfolio.fees.maker_rate), str(portfolio.fees.taker_rate)))
            db.commit()
        except BaseException:
            db.rollback()
            db.close()
            raise
        portfolio._db = db
        portfolio._persistent = True
        return portfolio

    @classmethod
    def open(cls, path):
        """Kayıtlı portföyü aç; eksik dosyayı oluşturma."""
        from pathlib import Path
        if not Path(path).is_file():
            raise TradeError("Portföy dosyası bulunamadı")
        db = sqlite3.connect(path, timeout=10, isolation_level=None)
        try:
            db.execute("BEGIN")
            portfolio = cls._load(db)
            db.commit()
        except BaseException:
            db.rollback()
            db.close()
            raise
        portfolio._db = db
        portfolio._persistent = True
        return portfolio

    @classmethod
    def _load(cls, db):
        row = db.execute("SELECT initial_cash, cash, quote, maker_rate, taker_rate FROM portfolio_meta WHERE id=1").fetchone()
        if row is None:
            raise TradeError("Portföy başlatılmamış")
        initial, cash, quote, maker, taker = row
        portfolio = cls(cash=Decimal(cash), fees=FeeSchedule(maker, taker), quote=quote)
        portfolio.initial_cash = Decimal(initial)
        portfolio.positions = {symbol: Position(Decimal(qty), Decimal(cost)) for symbol, qty, cost in db.execute("SELECT symbol, quantity, avg_cost FROM positions")}
        portfolio.trades = [Trade(datetime.fromisoformat(t), symbol, side, Decimal(qty), Decimal(price), Decimal(fee), Decimal(pnl)) for t, symbol, side, qty, price, fee, pnl in db.execute("SELECT timestamp, symbol, side, quantity, price, fee, realized_pnl FROM trades ORDER BY id")]
        return portfolio

    def _ensure_open(self):
        if getattr(self, "_persistent", False) and self._db is None:
            raise TradeError("Kalıcı portföy kapatılmış; işlem için yeniden açın")

    def close(self):
        if self._db is not None:
            self._db.close()
            self._db = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _persistent_trade(self, side, symbol, quantity, price, *, taker, timestamp):
        db = self._db
        db.execute("BEGIN IMMEDIATE")
        try:
            current = self._load(db)
            trade = getattr(current, side)(symbol, quantity, price, taker=taker, timestamp=timestamp)
            db.execute("UPDATE portfolio_meta SET cash=? WHERE id=1", (str(current.cash),))
            db.execute("DELETE FROM positions")
            db.executemany("INSERT INTO positions VALUES (?, ?, ?)", [(s, str(p.quantity), str(p.avg_cost)) for s, p in current.positions.items()])
            db.execute("INSERT INTO trades (timestamp, symbol, side, quantity, price, fee, realized_pnl) VALUES (?, ?, ?, ?, ?, ?, ?)", (trade.timestamp.isoformat(), trade.symbol, trade.side, str(trade.quantity), str(trade.price), str(trade.fee), str(trade.realized_pnl)))
            db.commit()
        except BaseException:
            db.rollback()
            raise
        self.cash, self.positions, self.trades = current.cash, current.positions, current.trades
        self.initial_cash, self.quote, self.fees = current.initial_cash, current.quote, current.fees
        return trade

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
        if not quantity.is_finite() or quantity <= 0:
            raise TradeError("Miktar pozitif olmalı")
        if not price.is_finite() or price <= 0:
            raise TradeError("Fiyat pozitif olmalı")
        return quantity, price

    def _record(self, timestamp, symbol, side, quantity, price, fee, realized) -> Trade:
        trade = Trade(timestamp or datetime.now(timezone.utc), symbol, side,
                      quantity, price, fee, realized)
        self.trades.append(trade)
        return trade
