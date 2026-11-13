"""Bir SQLite dosyasında tek sanal hesap; Decimal değerleri kayıpsız TEXT tutulur."""
from datetime import datetime, timezone
from decimal import Decimal
import json
import sqlite3
from pathlib import Path

from .fees import D, FeeSchedule
from .portfolio import Portfolio, Position, Trade
from .risk import RiskLimits, RiskError
from .policy import encode_policy, decode_policy


class SQLitePortfolio:
    """buy/sell atomiktir. portfolio özelliği bağımsız bir okuma kopyasıdır.

    Her yazım BEGIN IMMEDIATE altında güncel durumu yükler; başka bağlantının
    işlemleri eski bellek durumuyla ezilmez. Bağlantı aynı iş parçacığında kullanılır.
    """

    def __init__(self, path, *, initial_cash=0, fees=None, quote="USDT", risk=None, clock=None):
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
            is_new = self._db.execute("SELECT 1 FROM account").fetchone() is None
            self._ensure_policy_schema()
            if is_new:
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
                if risk is not None:
                    self._insert_policy(risk)
            elif risk is not None:
                self._verify_requested_policy(risk)
            self._db.commit()
        except BaseException:
            self._db.rollback()
            self._db.close()
            raise

    @classmethod
    def open(cls, path, *, risk=None, clock=None):
        """Var olan hesabı aç; eksik dosya veya şema oluşturma."""
        account = cls.__new__(cls)
        account._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)
        uri = Path(path).resolve().as_uri() + "?mode=rw"
        account._db = sqlite3.connect(uri, uri=True, isolation_level=None)
        try:
            account._db.execute("BEGIN IMMEDIATE")
            account._load()  # Uyumsuz dosyada şema oluşturmadan önce doğrula.
            account._ensure_policy_schema()
            if risk is not None:
                account._verify_requested_policy(risk)
            account._db.commit()
        except BaseException:
            account._db.rollback()
            account.close()
            raise
        return account

    def _ensure_policy_schema(self):
        self._db.execute("""CREATE TABLE IF NOT EXISTS risk_policies (
            version INTEGER PRIMARY KEY, schema_version INTEGER NOT NULL,
            policy TEXT NOT NULL, changed_at TEXT NOT NULL)""")
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(trades)")}
        if "risk_version" not in columns:
            self._db.execute("ALTER TABLE trades ADD COLUMN risk_version INTEGER")

    def _read_policy(self):
        row = self._db.execute("SELECT version,schema_version,policy FROM risk_policies ORDER BY version DESC LIMIT 1").fetchone()
        if row is None:
            raise RiskError("Hesapta risk politikası yok; önce açıkça politika tanımlayın")
        version, schema, text = row
        if schema != 1:
            raise RiskError("Desteklenmeyen risk politikası sürümü")
        try:
            return version, decode_policy(text)
        except (ValueError, TypeError, ArithmeticError, OverflowError) as exc:
            raise RiskError("Kayıtlı risk politikası bozuk; işlem durduruldu") from exc

    def _verify_requested_policy(self, risk):
        _, stored = self._read_policy()
        if stored != risk:
            raise RiskError("Verilen politika kayıtlı politikadan farklı; risk-set ile açıkça değiştirin")

    def _insert_policy(self, risk):
        encoded = encode_policy(risk)
        version = self._db.execute("SELECT COALESCE(MAX(version),0)+1 FROM risk_policies").fetchone()[0]
        self._db.execute("INSERT INTO risk_policies VALUES (?,1,?,?)",
                         (version, encoded, datetime.now(timezone.utc).isoformat()))
        return version

    @property
    def risk(self):
        return self._read_policy()[1]

    def set_risk(self, risk, *, expected_version):
        """Bilinçli politika değişikliği; sürüm geçmişini korur."""
        if type(expected_version) is not int or expected_version < 0:
            raise ValueError("Beklenen risk sürümü negatif olmayan tam sayı olmalı")
        self._db.execute("BEGIN IMMEDIATE")
        try:
            current = self._db.execute("SELECT COALESCE(MAX(version),0) FROM risk_policies").fetchone()[0]
            if current != expected_version:
                raise RiskError("Risk sürümü değişti; güncel politikayı yeniden okuyun")
            version = self._insert_policy(risk)
            self._db.commit()
            return version
        except BaseException:
            self._db.rollback()
            raise

    def policy_status(self):
        self._db.execute("BEGIN")
        try:
            version, risk = self._read_policy()
            self._db.commit()
            return version, risk
        except BaseException:
            self._db.rollback()
            raise

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
        if timestamp is not None:
            if not isinstance(timestamp, datetime) or timestamp.utcoffset() is None:
                raise ValueError("İşlem zamanı saat dilimi içermeli")
            timestamp = timestamp.astimezone(timezone.utc)
        self._db.execute("BEGIN IMMEDIATE")
        try:
            version, risk = self._read_policy()
            quantity, price = risk.check(symbol, quantity, price)
            p = self._load()
            # Kilit beklerken fiyat eskimiş olabilir; kontrolü kilitten sonra yap.
            risk.check_price_time(price_observed_at, now=self._clock())
            trade = getattr(p, side)(symbol, quantity, price, taker=taker, timestamp=timestamp)
            if side == "buy":
                risk.check_after_buy(p, symbol, price)
            positions = json.dumps({s: [str(pos.quantity), str(pos.avg_cost)]
                                    for s, pos in p.positions.items()})
            self._db.execute("UPDATE account SET cash=?, positions=? WHERE id=1",
                             (str(p.cash), positions))
            self._db.execute("""INSERT INTO trades
                (timestamp,symbol,side,quantity,price,fee,realized_pnl,risk_version)
                VALUES (?,?,?,?,?,?,?,?)""", (trade.timestamp.isoformat(), trade.symbol,
                trade.side, str(trade.quantity), str(trade.price), str(trade.fee), str(trade.realized_pnl), version))
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
