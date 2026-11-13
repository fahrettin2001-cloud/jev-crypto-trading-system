from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from jev import FeeSchedule, RiskError, RiskLimits, SQLitePortfolio
from jev.market import PriceObservation


class PortfolioLimitTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.now = datetime(2026, 11, 13, 10, tzinfo=timezone.utc)
        self.path = Path(temp.name)/'account.db'
        self.account = SQLitePortfolio(self.path, initial_cash=10000,
            risk=RiskLimits(), fees=FeeSchedule(0,0), clock=lambda:self.now)
        self.addCleanup(self.account.close)

    def test_daily_gross_loss_blocks_buys_but_allows_sells(self):
        self.account.set_risk(RiskLimits(max_daily_realized_loss=100))
        self.account.buy('BTCUSDT', 2, 500)
        # Kullanıcının geçmiş timestamp vermesi gerçek yürütme gününü değiştirmez.
        self.account.sell('BTCUSDT', 1, 400, timestamp=self.now-timedelta(days=10))
        before = self.account.portfolio
        with self.assertRaises(RiskError):
            self.account.buy('ETHUSDT', 1, 100)
        self.assertEqual(self.account.portfolio, before)
        self.account.sell('BTCUSDT', 1, 600)  # kazanç günlük kaybı silmez
        with SQLitePortfolio.open(self.path, clock=lambda:self.now) as reopened:
            with self.assertRaises(RiskError):
                reopened.buy('ETHUSDT', 1, 100)
        self.now += timedelta(days=1)
        self.account.buy('ETHUSDT', 1, 100)

    def test_total_value_requires_all_fresh_other_prices(self):
        self.account.buy('BTCUSDT', 1, 400)
        limits = RiskLimits(max_total_position_notional=500, max_price_age=timedelta(seconds=30))
        self.account.set_risk(limits)
        before = self.account.portfolio
        with self.assertRaises(RiskError):
            self.account.buy('ETHUSDT', 1, 100, price_observed_at=self.now)
        stale = PriceObservation('BTCUSDT', 400, self.now-timedelta(seconds=31), self.now)
        with self.assertRaises(RiskError):
            self.account.buy('ETHUSDT', 1, 100, price_observed_at=self.now, market_prices={'BTCUSDT':stale})
        fresh = PriceObservation('BTCUSDT', 400, self.now, self.now)
        with self.assertRaises(RiskError):
            self.account.buy('ETHUSDT', 1, 101, price_observed_at=self.now, market_prices={'BTCUSDT':fresh})
        self.assertEqual(self.account.portfolio, before)
        self.account.buy('ETHUSDT', 1, 100, price_observed_at=self.now, market_prices={'BTCUSDT':fresh})
        self.assertEqual(len(self.account.portfolio.positions), 2)

    def test_total_limit_requires_freshness_configuration(self):
        with self.assertRaises(ValueError):
            RiskLimits(max_total_position_notional=1000)
