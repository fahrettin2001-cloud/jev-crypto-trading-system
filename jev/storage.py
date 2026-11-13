"""Bir SQLite dosyasında tek sanal hesap; Decimal değerleri kayıpsız TEXT tutulur."""
from datetime import datetime, timezone
from decimal import Decimal
import json
import sqlite3
from pathlib import Path

from .fees import D, FeeSchedule
from .portfolio import Portfolio, Position, Trade
from .risk import RiskLimits


class SQLitePortfolio:
    """buy/sell atomiktir. portfolio özelliği bağımsız bir okuma kopyasıdır.

    Her yazım BEGIN IMMEDIATE altında güncel durumu yükler; başka bağlantının
    işlemleri eski bellek durumuyla ezilmez. Bağlantı aynı iş parçacığında kullanılır.
    """

    def __init__(self, path, *, initial_cash=0, fees=None, quote="USDT", risk=None, clock=None):
        self.risk = risk if risk is not None else RiskLimits()
        self._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)
        self._db = sqlite3.connect(path, isolation_level=None)
        try:
            self._db.execute("BEGIN IMMEDIATE")
            self._db.execute("""CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY CHECK(id=1), cash TEXT NOT NULL,
                initial_cash TEXT NOT NULL, quote TEXT NOT NULL,
                maker_rate TEXT NOT NULL, taker_rate TEXT NOT NULL,
                positions TEXT NOT NULL)""")
            self._db.execute("""CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, symbol TEXT NOT NULL,
                side TEXT NOT NULL CHECK(side IN ('BUY','SELL')), quantity TEXT NOT NULL,
                price TEXT NOT NULL, fee TEXT NOT NULL, realized_pnl TEXT NOT NULL)""")
            if self._db.execute("SELECT 1 FROM account").fetchone() is None:
                cash = D(initial_cash)
                if not cash.is_finite() or cash < 0:
                    raise ValueError("Başlangıç nakdi sonlu ve negatif olmayan değer olmalı")
                p = Portfolio(cash, fees=fees or FeeSchedule(), quote=quote)
                for rate in (p.fees.maker_rate, p.fees.taker_rate):
                    if not rate.is_finite():
                        raise ValueError("Komisyon sonlu olmalı")
                self._db.execute("INSERT INTO account VALUES (1,?,?,?,?,?,?)",
                                 (str(p.cash), str(p.initial_cash), p.quote,
                                  str(p.fees.maker_rate), str(p.fees.taker_rate), '{}'))
            self._db.commit()
        except BaseException:
            self._db.rollback()
            self._db.close()
            raise

    @classmethod
    def open(cls, path, *, risk=None, clock=None):
        """Var olan hesabı aç; eksik dosya veya şema oluşturma."""
        account = cls.__new__(cls)
        account.risk = risk if risk is not None else RiskLimits()
        account._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)
        uri = Path(path).resolve().as_uri() + "?mode=rw"
        account._db = sqlite3.connect(uri, uri=True, isolation_level=None)
        try:
            account.portfolio  # Şemayı ve kayıtlı hesabı doğrula.
        except BaseException:
            account.close()
            raise
        return account

    def _load(self):
        cash, initial, quote, maker, taker, positions = self._db.execute(
            "SELECT cash,initial_cash,quote,maker_rate,taker_rate,positions FROM account WHERE id=1"
        ).fetchone()
        p = Portfolio(Decimal(cash), fees=FeeSchedule(maker, taker), quote=quote)
        p.initial_cash = Decimal(initial)
        p.positions = {s: Position(Decimal(q), Decimal(c))
                       for s, (q, c) in json.loads(positions).items()}
        p.trades = [Trade(datetime.fromisoformat(ts), symbol, side, Decimal(q),
                          Decimal(price), Decimal(fee), Decimal(pnl))
                    for ts, symbol, side, q, price, fee, pnl in self._db.execute(
                        "SELECT timestamp,symbol,side,quantity,price,fee,realized_pnl FROM trades ORDER BY id")]
        return p

    @property
    def portfolio(self):
        self._db.execute("BEGIN")
        try:
            p = self._load()
            self._db.commit()
            return p
        except BaseException:
            self._db.rollback()
            raise

    def _trade(self, side, symbol, quantity, price, *, taker=True, timestamp=None,
               price_observed_at=None):
        quantity, price = self.risk.check(symbol, quantity, price)
        if timestamp is not None:
            if not isinstance(timestamp, datetime) or timestamp.utcoffset() is None:
                raise ValueError("İşlem zamanı saat dilimi içermeli")
            timestamp = timestamp.astimezone(timezone.utc)
        self._db.execute("BEGIN IMMEDIATE")
        try:
            p = self._load()
            # Kilit beklerken fiyat eskimiş olabilir; kontrolü kilitten sonra yap.
            self.risk.check_price_time(price_observed_at, now=self._clock())
            trade = getattr(p, side)(symbol, quantity, price, taker=taker, timestamp=timestamp)
            if side == "buy":
                self.risk.check_after_buy(p, symbol, price)
            positions = json.dumps({s: [str(pos.quantity), str(pos.avg_cost)]
                                    for s, pos in p.positions.items()})
            self._db.execute("UPDATE account SET cash=?, positions=? WHERE id=1",
                             (str(p.cash), positions))
            self._db.execute("""INSERT INTO trades
                (timestamp,symbol,side,quantity,price,fee,realized_pnl)
                VALUES (?,?,?,?,?,?,?)""", (trade.timestamp.isoformat(), trade.symbol,
                trade.side, str(trade.quantity), str(trade.price), str(trade.fee), str(trade.realized_pnl)))
            self._db.commit()
            return trade
        except BaseException:
            self._db.rollback()
            raise

    def buy(self, symbol, quantity, price, *, taker=True, timestamp=None,
            price_observed_at=None):
        return self._trade("buy", symbol, quantity, price, taker=taker, timestamp=timestamp,
                           price_observed_at=price_observed_at)

    def sell(self, symbol, quantity, price, *, taker=True, timestamp=None,
             price_observed_at=None):
        return self._trade("sell", symbol, quantity, price, taker=taker, timestamp=timestamp,
                           price_observed_at=price_observed_at)

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
