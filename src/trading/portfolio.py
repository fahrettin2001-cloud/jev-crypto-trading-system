"""Persistent paper portfolio with atomic SQLite updates."""

import sqlite3
from decimal import Decimal, Inexact, InvalidOperation, localcontext


class TradeError(ValueError):
    """An invalid or unfundable paper trade."""


def _decimal(value, name, *, positive=False):
    # Floats have already lost decimal precision; require exact input instead.
    if isinstance(value, (float, bool)):
        raise TradeError(f"{name} must be an exact decimal value")
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise TradeError(f"invalid {name}") from None
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise TradeError(f"invalid {name}")
    # Bound input size so the fixed arithmetic precision below remains exact.
    if len(result.as_tuple().digits) > 28 or abs(result.as_tuple().exponent) > 28 or result.adjusted() > 28:
        raise TradeError(f"{name} is too large or precise")
    return result


def _symbol(value):
    if not isinstance(value, str) or not value.isascii() or not value.isalnum() or len(value) > 20:
        raise TradeError("invalid asset symbol")
    return value.upper()


class Portfolio:
    """A single portfolio; balances and its ledger share one database transaction."""

    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS balances (asset TEXT PRIMARY KEY, amount TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                side TEXT NOT NULL, asset TEXT NOT NULL, quote_asset TEXT NOT NULL,
                quantity TEXT NOT NULL, price TEXT NOT NULL, fee_rate TEXT NOT NULL,
                fee TEXT NOT NULL, total TEXT NOT NULL
            );
        """)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def initialize(self, cash, quote_asset="USDT"):
        cash = _decimal(cash, "cash")
        quote_asset = _symbol(quote_asset)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute("SELECT 1 FROM settings WHERE key = 'quote_asset'").fetchone():
                raise TradeError("portfolio is already initialized")
            self.db.execute("INSERT INTO settings VALUES ('quote_asset', ?)", (quote_asset,))
            self.db.execute("INSERT INTO balances VALUES (?, ?)", (quote_asset, str(cash)))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def _quote(self):
        row = self.db.execute("SELECT value FROM settings WHERE key = 'quote_asset'").fetchone()
        if row is None:
            raise TradeError("portfolio is not initialized")
        return row[0]

    def balances(self):
        self._quote()
        return {asset: Decimal(amount) for asset, amount in self.db.execute("SELECT asset, amount FROM balances ORDER BY asset")}

    def history(self):
        self._quote()
        self.db.row_factory = sqlite3.Row
        try:
            rows = self.db.execute("SELECT * FROM trades ORDER BY id").fetchall()
            return [dict(row) for row in rows]
        finally:
            self.db.row_factory = None

    def trade(self, side, asset, quantity, price, fee_rate="0"):
        if not isinstance(side, str) or side.lower() not in ("buy", "sell"):
            raise TradeError("side must be buy or sell")
        side = side.lower()
        asset = _symbol(asset)
        quantity = _decimal(quantity, "quantity", positive=True)
        price = _decimal(price, "price", positive=True)
        fee_rate = _decimal(fee_rate, "fee rate")
        if fee_rate > 1:
            raise TradeError("fee rate must be between 0 and 1")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            quote = self._quote()
            if asset == quote:
                raise TradeError("asset and quote asset must differ")
            def balance(symbol):
                row = self.db.execute("SELECT amount FROM balances WHERE asset = ?", (symbol,)).fetchone()
                return Decimal(row[0]) if row else Decimal(0)
            # Inputs are bounded above; this precision accommodates repeated updates.
            with localcontext() as ctx:
                ctx.prec = 256
                ctx.traps[Inexact] = True
                cash, holdings = balance(quote), balance(asset)
                gross = quantity * price
                fee = gross * fee_rate
                total = gross + fee if side == "buy" else gross - fee
                if side == "buy":
                    if cash < total:
                        raise TradeError("insufficient cash")
                    cash, holdings = cash - total, holdings + quantity
                else:
                    if holdings < quantity:
                        raise TradeError("insufficient asset balance")
                    cash, holdings = cash + total, holdings - quantity
                for symbol, amount in ((quote, cash), (asset, holdings)):
                    self.db.execute("INSERT INTO balances VALUES (?, ?) ON CONFLICT(asset) DO UPDATE SET amount=excluded.amount", (symbol, str(amount)))
                self.db.execute("INSERT INTO trades (side, asset, quote_asset, quantity, price, fee_rate, fee, total) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                (side, asset, quote, str(quantity), str(price), str(fee_rate), str(fee), str(total)))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
