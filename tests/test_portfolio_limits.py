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
        self.account.set_risk(RiskLimits(max_daily_realized_loss=100), expected_version=1)
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
        self.account.set_risk(limits, expected_version=1)
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

    def test_legacy_loss_yesterday_does_not_permanently_lock_account(self):
        self.account.set_risk(RiskLimits(max_daily_realized_loss=50), expected_version=1)
        self.now -= timedelta(days=1)
        self.account.buy('BTCUSDT', 1, 1000, timestamp=self.now)
        self.account.sell('BTCUSDT', 1, 900, timestamp=self.now)
        self.account._db.execute('UPDATE trades SET executed_at=NULL')
        history = self.account.portfolio.trades.copy()
        self.now += timedelta(days=1)
        with SQLitePortfolio.open(self.path, clock=lambda:self.now) as reopened:
            reopened.buy('ETHUSDT', 1, 100)
            self.assertEqual(reopened.portfolio.trades[:2], history)
            self.assertEqual(reopened._db.execute('SELECT count(*) FROM trades WHERE executed_at IS NULL').fetchone()[0], 2)

    def test_legacy_loss_today_still_blocks_new_buys(self):
        self.account.set_risk(RiskLimits(max_daily_realized_loss=50), expected_version=1)
        self.account.buy('BTCUSDT', 1, 1000, timestamp=self.now)
        self.account.sell('BTCUSDT', 1, 900, timestamp=self.now)
        self.account._db.execute('UPDATE trades SET executed_at=NULL')
        before = self.account.portfolio
        with self.assertRaises(RiskError):
            self.account.buy('ETHUSDT', 1, 100)
        self.assertEqual(self.account.portfolio, before)

    def test_legacy_time_is_compared_in_utc(self):
        self.account.set_risk(RiskLimits(max_daily_realized_loss=50), expected_version=1)
        self.account.buy('BTCUSDT', 1, 1000, timestamp=self.now)
        self.account.sell('BTCUSDT', 1, 900, timestamp=self.now)
        # 14 Kasım 01:00 TR = 13 Kasım 22:00 UTC. Bugün 14 Kasım UTC.
        self.account._db.execute("UPDATE trades SET executed_at=NULL,timestamp='2026-11-14T01:00:00+03:00'")
        self.now = datetime(2026, 11, 14, 0, 1, tzinfo=timezone.utc)
        self.account.buy('ETHUSDT', 1, 100)

    def test_profitable_position_can_sell_above_trade_limit(self):
        self.account.set_risk(RiskLimits(max_trade_notional=50), expected_version=1)
        self.account.buy('BTCUSDT', '0.0005', 90000)
        self.account.sell('BTCUSDT', '0.0005', 120000)
        self.assertEqual(self.account.portfolio.positions, {})
        with self.assertRaises(RiskError):
            self.account.buy('BTCUSDT', '0.0005', 120000)

    def test_sell_still_validates_symbol_quantity_and_freshness(self):
        self.account.set_risk(RiskLimits(max_trade_notional=50, allowed_symbols={'BTCUSDT'},
                              max_price_age=timedelta(seconds=30)), expected_version=1)
        self.account.buy('BTCUSDT', '0.0005', 90000, price_observed_at=self.now)
        before = self.account.portfolio
        for symbol, quantity, observed in (('ETHUSDT','0.0005',self.now),
                                           ('BTCUSDT',0,self.now),
                                           ('BTCUSDT','0.0005',self.now-timedelta(minutes=1))):
            with self.assertRaises(RiskError):
                self.account.sell(symbol, quantity, 120000, price_observed_at=observed)
        self.assertEqual(self.account.portfolio, before)
