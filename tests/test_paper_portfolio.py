import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from jev import FeeSchedule, Portfolio, TradeError


class PersistentPortfolioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "portfolio.sqlite3"
        self.p = Portfolio.create(self.path, "1000", FeeSchedule("0.002", "0.01"))

    def tearDown(self):
        self.p.close()
        self.temp.cleanup()

    def test_reopen_preserves_positions_fees_and_pnl(self):
        self.p.buy("BTCUSDT", "0.1", "1000")
        self.p.sell("BTCUSDT", "0.04", "1200", taker=False)
        expected = (self.p.cash, self.p.initial_cash, self.p.positions, self.p.trades, self.p.realized_pnl, self.p.total_fees, self.p.equity({"BTCUSDT": Decimal("1100")}))
        self.p.close()
        self.p = Portfolio.open(self.path)
        self.assertEqual((self.p.cash, self.p.initial_cash, self.p.positions, self.p.trades, self.p.realized_pnl, self.p.total_fees, self.p.equity({"BTCUSDT": Decimal("1100")})), expected)
        self.assertEqual(self.p.fees.maker_rate, Decimal("0.002"))
        self.p.sell("BTCUSDT", "0.01", "1100")
        self.assertEqual(self.p.positions["BTCUSDT"].quantity, Decimal("0.05"))

    def test_failed_trades_do_not_change_state(self):
        before = (self.p.cash, self.p.positions.copy(), self.p.trades.copy())
        for side, quantity, price in (("buy", "2", "1000"), ("sell", "1", "1"), ("buy", "0", "1"), ("buy", "1", "NaN")):
            with self.subTest(side=side, quantity=quantity, price=price), self.assertRaises(TradeError):
                getattr(self.p, side)("BTCUSDT", quantity, price)
            self.assertEqual((self.p.cash, self.p.positions, self.p.trades), before)
        with Portfolio.open(self.path) as opened:
            self.assertEqual((opened.cash, opened.positions, opened.trades), before)

    def test_database_failure_rolls_back_memory_and_disk(self):
        self.p.buy("BTCUSDT", "0.1", "1000")
        before = (self.p.cash, self.p.positions.copy(), self.p.trades.copy())
        self.p._db.execute("CREATE TRIGGER fail_trade BEFORE INSERT ON trades BEGIN SELECT RAISE(ABORT, 'simulated failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.p.sell("BTCUSDT", "0.04", "1000")
        self.assertEqual((self.p.cash, self.p.positions, self.p.trades), before)
        with Portfolio.open(self.path) as opened:
            self.assertEqual((opened.cash, opened.positions, opened.trades), before)

    def test_reinitialization_does_not_reset(self):
        with self.assertRaises(TradeError):
            Portfolio.create(self.path, "5000")
        with Portfolio.open(self.path) as opened:
            self.assertEqual(opened.cash, Decimal("1000"))

    def test_second_connection_checks_latest_balance(self):
        with Portfolio.open(self.path) as other:
            self.p.buy("BTCUSDT", "1", "600")
            with self.assertRaises(TradeError):
                other.buy("BTCUSDT", "1", "600")
            with Portfolio.open(self.path) as opened:
                self.assertEqual(opened.cash, Decimal("394"))
                self.assertEqual(len(opened.trades), 1)

    def test_missing_database_not_created(self):
        path = Path(self.temp.name) / "missing.sqlite3"
        with self.assertRaises(TradeError):
            Portfolio.open(path)
        self.assertFalse(path.exists())
