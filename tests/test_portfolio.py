import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from trading import Portfolio, TradeError


class PortfolioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "portfolio.sqlite3"
        self.portfolio = Portfolio(self.path)
        self.portfolio.initialize("1000")

    def tearDown(self):
        self.portfolio.close()
        self.temp.cleanup()

    def test_buy_sell_fees_and_history(self):
        self.portfolio.trade("buy", "btc", "0.1", "1000", "0.01")
        self.portfolio.trade("sell", "BTC", "0.04", "1200", "0.01")
        self.assertEqual(self.portfolio.balances(), {"BTC": Decimal("0.06"), "USDT": Decimal("946.52")})
        history = self.portfolio.history()
        self.assertEqual(len(history), 2)
        self.assertEqual((history[0]["side"], Decimal(history[0]["fee"]), Decimal(history[0]["total"])), ("buy", Decimal("1"), Decimal("101")))
        self.assertEqual((history[1]["side"], Decimal(history[1]["fee"]), Decimal(history[1]["total"])), ("sell", Decimal("0.48"), Decimal("47.52")))

    def test_reopen_restores_balances_and_history(self):
        self.portfolio.trade("buy", "ETH", "0.25", "100", "0.002")
        expected = self.portfolio.balances(), self.portfolio.history()
        self.portfolio.close()
        self.portfolio = Portfolio(self.path)
        self.assertEqual((self.portfolio.balances(), self.portfolio.history()), expected)
        self.portfolio.trade("sell", "ETH", "0.1", "120")
        self.assertEqual(self.portfolio.balances()["ETH"], Decimal("0.15"))

    def test_rejections_leave_balances_and_history_unchanged(self):
        cases = [("buy", "BTC", "2", "1000", "0"), ("sell", "BTC", "1", "1", "0"),
                 ("buy", "BTC", "0", "1", "0"), ("buy", "BTC", "1", "-1", "0"),
                 ("buy", "BTC", "1", "NaN", "0"), ("buy", "BTC", "1", "1", "1.1"),
                 ("buy", "USDT", "1", "1", "0"), ("buy", "BTC", 0.1, "1", "0")]
        before = self.portfolio.balances(), self.portfolio.history()
        for args in cases:
            with self.subTest(args=args), self.assertRaises(TradeError):
                self.portfolio.trade(*args)
            self.assertEqual((self.portfolio.balances(), self.portfolio.history()), before)

    def test_database_failure_after_balance_updates_rolls_back_everything(self):
        self.portfolio.db.execute("CREATE TRIGGER fail_trade BEFORE INSERT ON trades BEGIN SELECT RAISE(ABORT, 'simulated failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.portfolio.trade("buy", "BTC", "1", "100")
        self.assertEqual(self.portfolio.balances(), {"USDT": Decimal("1000")})
        self.assertEqual(self.portfolio.history(), [])
        with Portfolio(self.path) as reopened:
            self.assertEqual(reopened.balances(), {"USDT": Decimal("1000")})
            self.assertEqual(reopened.history(), [])

    def test_reinitialization_does_not_reset_portfolio(self):
        with self.assertRaises(TradeError):
            self.portfolio.initialize("5000")
        self.assertEqual(self.portfolio.balances(), {"USDT": Decimal("1000")})

    def test_concurrent_connections_use_latest_balance(self):
        with Portfolio(self.path) as other:
            self.portfolio.trade("buy", "BTC", "1", "600")
            with self.assertRaises(TradeError):
                other.trade("buy", "BTC", "1", "600")
            self.assertEqual(len(other.history()), 1)
            self.assertEqual(other.balances()["USDT"], Decimal("400"))


if __name__ == "__main__":
    unittest.main()
