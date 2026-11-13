from contextlib import closing
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from jev.fees import FeeSchedule
from jev.portfolio import TradeError
from jev.risk import RiskError, RiskLimits
from jev.storage import SQLitePortfolio


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'portfolio.db'
        self.store = SQLitePortfolio(self.path, initial_cash='10000',
                                    fees=FeeSchedule('0.0005', '0.001'), risk=RiskLimits())
        self.addCleanup(self.store.close)

    def test_restart_restores_all_account_fields_and_history(self):
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.store.buy('BTCUSDT', '0.1', '50000', timestamp=ts, taker=False)
        self.store.sell('BTCUSDT', '0.04', '55000', timestamp=ts)
        expected = self.store.portfolio
        with SQLitePortfolio(self.path, initial_cash=1, quote='OTHER') as reopened:
            actual = reopened.portfolio
            self.assertEqual(actual, expected)
            self.assertEqual(actual.initial_cash, Decimal('10000'))
            self.assertEqual(actual.total_fees, expected.total_fees)
            self.assertEqual(actual.realized_pnl, expected.realized_pnl)
            self.assertEqual(actual.trades[0].timestamp, ts)
            self.assertEqual(actual.fees.maker_rate, Decimal('0.0005'))
            self.assertEqual(actual.cash, Decimal('7195.30000'))
            reopened.sell('BTCUSDT', '0.06', '55000')
            self.assertEqual(reopened.portfolio.positions, {})

    def test_insufficient_cash_and_oversell_leave_database_unchanged(self):
        for method, qty, price in ((self.store.buy, 1, 10000),
                                   (self.store.sell, 1, 100)):
            before = self.store.portfolio
            with self.assertRaises(TradeError):
                method('BTCUSDT', qty, price)
            self.assertEqual(self.store.portfolio, before)
        with SQLitePortfolio(self.path) as reopened:
            self.assertEqual(reopened.portfolio.cash, Decimal('10000'))
            self.assertEqual(reopened.portfolio.trades, [])

    def test_insert_failure_rolls_back_balance_positions_and_trade(self):
        self.store.buy('BTCUSDT', '0.1', '50000')
        before = self.store.portfolio
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""CREATE TRIGGER fail_trade BEFORE INSERT ON trades
                BEGIN SELECT RAISE(ABORT, 'simulated disk write failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.sell('BTCUSDT', '0.1', '55000')
        self.assertEqual(self.store.portfolio, before)
        with SQLitePortfolio(self.path) as reopened:
            self.assertEqual(reopened.portfolio, before)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('DROP TRIGGER fail_trade')
        self.store.sell('BTCUSDT', '0.1', '55000')
        self.assertEqual(len(self.store.portfolio.trades), 2)

    def test_two_connections_use_latest_balance(self):
        with SQLitePortfolio(self.path) as second:
            self.store.buy('ETHUSDT', 1, 3000)
            second.buy('ETHUSDT', 1, 3000)
            with self.assertRaises(TradeError):
                self.store.buy('ETHUSDT', 2, 3000)
            self.assertEqual(second.portfolio.cash, Decimal('3994'))
            self.assertEqual(self.store.portfolio.positions['ETHUSDT'].quantity, 2)
            self.assertEqual(len(self.store.portfolio.trades), 2)

    def test_snapshot_mutation_cannot_change_saved_account(self):
        snapshot = self.store.portfolio
        snapshot.cash = Decimal('999999')
        snapshot.buy('ETHUSDT', 1, 3000)
        self.assertEqual(self.store.portfolio.cash, Decimal('10000'))
        self.assertEqual(self.store.portfolio.trades, [])

    def test_invalid_numbers_and_timestamp_rejected_without_writes(self):
        for value in ('NaN', 'sNaN', 'Infinity', '-Infinity', 'bad', 0, -1):
            for quantity, price in ((value, 100), (1, value)):
                with self.subTest(quantity=quantity, price=price):
                    with self.assertRaises(RiskError):
                        self.store.buy('BTCUSDT', quantity, price)
        with self.assertRaises(ValueError):
            self.store.buy('BTCUSDT', 1, 100, timestamp=datetime(2026, 1, 1))
        self.assertEqual(self.store.portfolio.trades, [])

    def test_risk_limits_apply_to_buy_and_sell(self):
        self.store.set_risk(RiskLimits('100', frozenset({'BTCUSDT'})), expected_version=1)
        self.store.buy('BTCUSDT', 1, 100)
        for method, symbol, price in ((self.store.buy, 'ETHUSDT', 10),
                                      (self.store.buy, 'BTCUSDT', 101),
                                      (self.store.sell, 'BTCUSDT', 101)):
            before = self.store.portfolio
            with self.assertRaises(RiskError):
                method(symbol, 1, price)
            self.assertEqual(self.store.portfolio, before)
        self.store.sell('BTCUSDT', 1, 100)

    def test_decimal_precision_survives_restart(self):
        self.store.buy('BTCUSDT', '0.000000000000123456789', '12345.67890123456789')
        with SQLitePortfolio(self.path) as reopened:
            self.assertEqual(reopened.portfolio, self.store.portfolio)

    def test_invalid_initial_balance_does_not_create_account(self):
        for cash in ('NaN', 'Infinity', '-1'):
            with self.assertRaises(ValueError):
                SQLitePortfolio(Path(self.tmp.name) / 'invalid.db', initial_cash=cash)
        with SQLitePortfolio(Path(self.tmp.name) / 'invalid.db', initial_cash=100) as valid:
            self.assertEqual(valid.portfolio.cash, 100)


class RiskTests(unittest.TestCase):
    def test_limit_configuration_rejects_invalid_values(self):
        for value in (0, -1, 'NaN', 'Infinity'):
            with self.assertRaises(ValueError):
                RiskLimits(value)

    def test_no_numeric_limit_is_assumed(self):
        self.assertEqual(RiskLimits().check('BTCUSDT', 2, 10000),
                         (Decimal('2'), Decimal('10000')))
        for symbol in ('', '  ', None):
            with self.assertRaises(RiskError):
                RiskLimits().check(symbol, 1, 1)
