from datetime import timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from jev import FeeSchedule, RiskError, RiskLimits, SQLitePortfolio


class PolicyPersistenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'account.db'

    def test_reopen_without_limits_preserves_restrictions(self):
        limits = RiskLimits(max_trade_notional='50', min_cash_reserve='100',
                            max_position_notional='75', allowed_symbols={'BTCUSDT'},
                            max_price_age=timedelta(seconds=30, microseconds=123))
        with SQLitePortfolio(self.path, initial_cash=1000, risk=limits) as account:
            self.assertEqual(account.policy_status(), (1, limits))
        with SQLitePortfolio.open(self.path) as account:
            self.assertEqual(account.risk, limits)
            with self.assertRaises(RiskError):
                account.buy('BTCUSDT', 1, 100)
            self.assertEqual(account.portfolio.cash, 1000)

    def test_no_policy_means_readable_but_no_trades(self):
        with SQLitePortfolio(self.path, initial_cash=1000) as account:
            self.assertEqual(account.portfolio.cash, 1000)
            for side in ('buy', 'sell'):
                with self.assertRaisesRegex(RiskError, 'politikası yok'):
                    getattr(account, side)('BTCUSDT', 1, 100)
            self.assertEqual(account.portfolio.trades, [])
            account.set_risk(RiskLimits(max_trade_notional=500), expected_version=0)
            account.buy('BTCUSDT', 1, 100)

    def test_open_cannot_weaken_or_replace_policy(self):
        with SQLitePortfolio(self.path, initial_cash=1000, risk=RiskLimits(max_trade_notional=50)):
            pass
        for opener in (SQLitePortfolio, SQLitePortfolio.open):
            with self.assertRaisesRegex(RiskError, 'farklı'):
                opener(self.path, risk=RiskLimits())
        with SQLitePortfolio.open(self.path) as account:
            self.assertEqual(account.risk.max_trade_notional, 50)

    def test_two_connections_read_latest_policy_and_trade_version(self):
        with SQLitePortfolio(self.path, initial_cash=1000, risk=RiskLimits()) as first:
            with SQLitePortfolio.open(self.path) as second:
                first.buy('BTCUSDT', 1, 100)
                second.set_risk(RiskLimits(max_trade_notional=50), expected_version=1)
                with self.assertRaises(RiskError):
                    first.buy('BTCUSDT', 1, 100)
                first.buy('BTCUSDT', 1, 40)
                with self.assertRaises(RiskError):
                    first.set_risk(RiskLimits(), expected_version=1)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT risk_version FROM trades ORDER BY id').fetchall(), [(1,), (2,)])
            self.assertEqual(db.execute('SELECT count(*) FROM risk_policies').fetchone()[0], 2)

    def test_corrupt_or_unknown_schema_fails_closed(self):
        with SQLitePortfolio(self.path, initial_cash=1000, risk=RiskLimits()) as account:
            for payload, schema in (('{}', 1), ('broken', 1), ('{}', 999)):
                with sqlite3.connect(self.path) as db:
                    db.execute('UPDATE risk_policies SET policy=?,schema_version=?', (payload, schema))
                with self.assertRaises(RiskError):
                    account.buy('BTCUSDT', 1, 100)
                self.assertEqual(account.portfolio.trades, [])

    def test_policy_write_failure_rolls_back(self):
        with SQLitePortfolio(self.path, initial_cash=1000, risk=RiskLimits(max_trade_notional=50)) as account:
            with sqlite3.connect(self.path) as db:
                db.execute("CREATE TRIGGER fail_policy BEFORE INSERT ON risk_policies BEGIN SELECT RAISE(ABORT,'failure'); END")
            with self.assertRaises(sqlite3.IntegrityError):
                account.set_risk(RiskLimits())
            self.assertEqual(account.risk.max_trade_notional, 50)

    def test_legacy_schema_migrates_without_inventing_policy(self):
        with SQLitePortfolio(self.path, initial_cash=1000, risk=RiskLimits()) as account:
            account.buy('BTCUSDT', 1, 100)
            expected = account.portfolio
        with sqlite3.connect(self.path) as db:
            db.execute('DROP TABLE risk_policies')
            db.execute('ALTER TABLE trades DROP COLUMN risk_version')
        with SQLitePortfolio.open(self.path) as account:
            self.assertEqual(account.portfolio, expected)
            with self.assertRaises(RiskError):
                account.buy('BTCUSDT', 1, 100)
            self.assertEqual(account.set_risk(RiskLimits(max_trade_notional=50), expected_version=0), 1)
        with sqlite3.connect(self.path) as db:
            self.assertIsNone(db.execute('SELECT risk_version FROM trades').fetchone()[0])
