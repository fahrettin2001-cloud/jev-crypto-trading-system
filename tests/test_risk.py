"""Risk reddinin hesabı değiştirmediğini gerçek SQLite dosyasında doğrular."""
from decimal import Decimal, localcontext
from pathlib import Path
import tempfile
import unittest

from jev import FeeSchedule, RiskError, RiskLimits, SQLitePortfolio


class ExtendedRiskTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'account.db'
        self.account = SQLitePortfolio(self.path, initial_cash=1000,
                                       fees=FeeSchedule('0', '0'), risk=RiskLimits())
        self.addCleanup(self.account.close)

    def assert_unchanged_after_rejection(self, quantity, price):
        before = self.account.portfolio
        with self.assertRaises(RiskError):
            self.account.buy('BTCUSDT', quantity, price)
        self.assertEqual(self.account.portfolio, before)
        with SQLitePortfolio(self.path) as reopened:
            self.assertEqual(reopened.portfolio, before)

    def test_cash_reserve_boundary_and_rejection(self):
        self.account.risk = RiskLimits(min_cash_reserve='500')
        self.account.buy('BTCUSDT', 1, 500)
        self.assertEqual(self.account.portfolio.cash, 500)
        self.assert_unchanged_after_rejection('0.01', 500)

    def test_cash_reserve_includes_fee(self):
        with SQLitePortfolio(Path(self.path.parent) / 'fees.db', initial_cash=1000,
                             risk=RiskLimits(min_cash_reserve=500)) as account:
            with self.assertRaises(RiskError):
                account.buy('BTCUSDT', 1, 500)
            self.assertEqual(account.portfolio.cash, 1000)
            self.assertEqual(account.portfolio.trades, [])

    def test_position_limit_uses_cumulative_quantity(self):
        self.account.risk = RiskLimits(max_position_notional=500)
        self.account.buy('BTCUSDT', 2, 100)
        self.account.buy('BTCUSDT', 3, 100)
        self.assertEqual(self.account.portfolio.positions['BTCUSDT'].quantity, 5)
        self.assert_unchanged_after_rejection(1, 100)

    def test_position_limit_uses_new_price_not_average_cost(self):
        self.account.buy('BTCUSDT', 1, 100)
        self.account.risk = RiskLimits(max_position_notional=500)
        self.assert_unchanged_after_rejection(1, 300)

    def test_position_limit_is_per_symbol(self):
        self.account.risk = RiskLimits(max_position_notional=500)
        self.account.buy('BTCUSDT', 1, 400)
        self.account.buy('ETHUSDT', 1, 400)
        self.assertEqual(len(self.account.portfolio.positions), 2)

    def test_sell_allowed_when_account_already_exceeds_new_limits(self):
        self.account.buy('BTCUSDT', 5, 100)
        self.account.risk = RiskLimits(min_cash_reserve=900, max_position_notional=100)
        self.account.sell('BTCUSDT', 1, 100)
        self.assertEqual(self.account.portfolio.cash, 600)
        self.assertEqual(self.account.portfolio.positions['BTCUSDT'].quantity, 4)
        self.account.sell('BTCUSDT', 4, 100)
        self.assertEqual(self.account.portfolio.positions, {})

    def test_limits_reapplied_after_restart(self):
        self.account.buy('BTCUSDT', 4, 100)
        self.account.set_risk(RiskLimits(max_position_notional=400))
        with SQLitePortfolio(self.path) as reopened:
            with self.assertRaises(RiskError):
                reopened.buy('BTCUSDT', 1, 100)
            self.assertEqual(len(reopened.portfolio.trades), 1)

    def test_invalid_configuration(self):
        for name in ('min_cash_reserve', 'max_position_notional', 'max_trade_notional'):
            for value in ('NaN', 'sNaN', 'Infinity', '-1', 'invalid', object()):
                with self.subTest(name=name, value=value):
                    with self.assertRaises(ValueError):
                        RiskLimits(**{name: value})
        with self.assertRaises(ValueError):
            RiskLimits(max_position_notional=0)
        self.assertEqual(RiskLimits(min_cash_reserve=0).min_cash_reserve, Decimal(0))

    def test_numeric_overflow_is_risk_rejection(self):
        with localcontext() as context:
            context.Emax = 3
            with self.assertRaises(RiskError):
                RiskLimits().check('BTCUSDT', '1e3', '1e3')
        self.assertEqual(self.account.portfolio.trades, [])
