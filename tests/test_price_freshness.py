"""Fiyat güncelliği hesabı değiştirmeden, karar saatine göre denetlenir."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jev import RiskError, RiskLimits, SQLitePortfolio


class PriceFreshnessTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'account.db'
        self.now = datetime(2026, 11, 13, 10, tzinfo=timezone.utc)
        self.limits = RiskLimits(max_price_age=timedelta(seconds=30))
        self.account = SQLitePortfolio(self.path, initial_cash=1000, risk=self.limits,
                                       clock=lambda: self.now)
        self.addCleanup(self.account.close)

    def assert_rejected_unchanged(self, observed_at, *, side='buy', **kwargs):
        before = self.account.portfolio
        with self.assertRaises(RiskError):
            getattr(self.account, side)('BTCUSDT', 1, 100,
                                       price_observed_at=observed_at, **kwargs)
        self.assertEqual(self.account.portfolio, before)
        with SQLitePortfolio(self.path, risk=self.limits, clock=lambda: self.now) as reopened:
            self.assertEqual(reopened.portfolio, before)

    def test_current_and_boundary_prices_accepted(self):
        self.account.buy('BTCUSDT', 1, 100, price_observed_at=self.now)
        self.account.buy('BTCUSDT', 1, 100,
                         price_observed_at=self.now - timedelta(seconds=30))
        self.assertEqual(len(self.account.portfolio.trades), 2)

    def test_missing_and_invalid_observation_rejected(self):
        for observed_at in (None, '2026-11-13', self.now.replace(tzinfo=None)):
            with self.subTest(observed_at=observed_at):
                self.assert_rejected_unchanged(observed_at)

    def test_stale_and_future_observation_rejected(self):
        for delta in (timedelta(seconds=-30, microseconds=-1), timedelta(microseconds=1)):
            with self.subTest(delta=delta):
                self.assert_rejected_unchanged(self.now + delta)

    def test_trade_timestamp_cannot_bypass_check(self):
        old = self.now - timedelta(days=1)
        self.assert_rejected_unchanged(old, timestamp=old)

    def test_equivalent_timezones_accepted(self):
        observed_at = self.now.astimezone(timezone(timedelta(hours=3)))
        self.account.buy('BTCUSDT', 1, 100, price_observed_at=observed_at)
        self.assertEqual(len(self.account.portfolio.trades), 1)

    def test_sell_requires_fresh_price_too(self):
        self.account.buy('BTCUSDT', 1, 100, price_observed_at=self.now)
        self.assert_rejected_unchanged(None, side='sell')
        self.assert_rejected_unchanged(self.now - timedelta(seconds=31), side='sell')
        self.account.sell('BTCUSDT', 1, 100, price_observed_at=self.now)
        self.assertEqual(self.account.portfolio.positions, {})

    def test_restarted_account_rejects_expired_price(self):
        observed_at = self.now
        self.account.buy('BTCUSDT', 1, 100, price_observed_at=observed_at)
        self.now += timedelta(seconds=31)
        with SQLitePortfolio(self.path, risk=self.limits, clock=lambda: self.now) as reopened:
            with self.assertRaises(RiskError):
                reopened.buy('BTCUSDT', 1, 100, price_observed_at=observed_at)
            self.assertEqual(len(reopened.portfolio.trades), 1)

    def test_clock_checked_after_loading_under_write_lock(self):
        observed_at = self.now
        original_load = self.account._load

        def slow_load():
            account = original_load()
            self.now += timedelta(seconds=31)
            return account

        with patch.object(self.account, '_load', side_effect=slow_load):
            with self.assertRaises(RiskError):
                self.account.buy('BTCUSDT', 1, 100, price_observed_at=observed_at)
        self.assertEqual(self.account.portfolio.trades, [])
        self.assertEqual(self.account.portfolio.cash, 1000)

    def test_invalid_clock_fails_closed(self):
        for invalid in (None, self.now.replace(tzinfo=None)):
            with self.subTest(clock=invalid):
                with patch.object(self.account, '_clock', return_value=invalid):
                    self.assert_rejected_unchanged(self.now)

    def test_default_clock_is_utc_and_not_trade_timestamp(self):
        with SQLitePortfolio(Path(self.path.parent) / 'real-clock.db', initial_cash=1000,
                             risk=RiskLimits(max_price_age=timedelta(days=1))) as account:
            self.assertEqual(account._clock().utcoffset(), timedelta(0))
            observed_at = datetime.now(timezone.utc)
            account.buy('BTCUSDT', 1, 100, price_observed_at=observed_at)
            with self.assertRaises(RiskError):
                account.buy('BTCUSDT', 1, 100, price_observed_at=observed_at-timedelta(days=2))

    def test_opt_in_preserves_existing_offline_workflow(self):
        self.account.risk = RiskLimits()
        self.account.buy('BTCUSDT', 1, 100)
        self.assertEqual(len(self.account.portfolio.trades), 1)

    def test_missing_price_rejected_without_account_change(self):
        before = self.account.portfolio
        with self.assertRaises(RiskError):
            self.account.buy("BTCUSDT", 1, None, price_observed_at=self.now)
        self.assertEqual(self.account.portfolio, before)

    def test_invalid_age_limit(self):
        for age in (0, 30, '30', timedelta(0), timedelta(seconds=-1)):
            with self.subTest(age=age):
                with self.assertRaises(ValueError):
                    RiskLimits(max_price_age=age)
