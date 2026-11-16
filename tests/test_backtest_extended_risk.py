"""PR #11 risk genişletmelerinin Görev 4 motoruyla birlikte çalışması."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from jev.backtest import BacktestConfig, run_backtest
from jev import FeeSchedule, RiskLimits
from jev.strategy import Bar, OrderIntent, BUY, SELL


class Scripted:
    name = 'risk-entegrasyonu'

    def __init__(self, plan):
        self.plan, self.i = plan, 0

    def on_bar(self, bar, view):
        result = self.plan.get(self.i, [])
        self.i += 1
        return result


class BacktestExtendedRiskTests(unittest.TestCase):
    def test_daily_loss_blocks_same_day_and_allows_next_day(self):
        start = datetime(2026, 11, 13, 10, tzinfo=timezone.utc)
        times = [start, start+timedelta(hours=1), start+timedelta(hours=2),
                 start+timedelta(days=1)]
        bars = [Bar(t, {'BTCUSDT':price}) for t,price in zip(times, [1000,900,900,900])]
        plan = {0:[OrderIntent('BTCUSDT',BUY,quantity=1)],
                1:[OrderIntent('BTCUSDT',SELL,quantity='ALL')],
                2:[OrderIntent('BTCUSDT',BUY,quantity=1)],
                3:[OrderIntent('BTCUSDT',BUY,quantity=1)]}
        result = run_backtest(bars, Scripted(plan), BacktestConfig(initial_cash=5000,
            fees=FeeSchedule(0,0), risk=RiskLimits(max_daily_realized_loss=50), execution='same_bar'))
        self.assertEqual([t.side for t in result.trades], [BUY,SELL,BUY])
        self.assertEqual(result.trades[-1].timestamp, times[-1])
        self.assertEqual(len(result.rejections), 1)
        self.assertIn('Günlük', result.rejections[0].reason)

    def test_total_position_limit_uses_open_not_future_close(self):
        start = datetime(2026, 11, 13, tzinfo=timezone.utc)
        bars = [Bar(start+timedelta(hours=i), {'BTCUSDT':100, 'ETHUSDT':100},
                    opens={'BTCUSDT':400 if i==2 else 100,'ETHUSDT':100},
                    highs={'BTCUSDT':400 if i==2 else 100,'ETHUSDT':100})
                for i in range(3)]
        plan = {0:[OrderIntent('BTCUSDT',BUY,quantity=1)],
                1:[OrderIntent('ETHUSDT',BUY,quantity=1)]}
        result = run_backtest(bars, Scripted(plan), BacktestConfig(initial_cash=5000,
            fees=FeeSchedule(0,0), risk=RiskLimits(max_total_position_notional=450,
            max_price_age=timedelta(seconds=30))))
        self.assertEqual(len(result.trades), 1)
        self.assertEqual(result.trades[0].symbol, 'BTCUSDT')
        self.assertIn('Toplam', result.rejections[0].reason)
        # Henüz bilinmeyen düşük kapanış (100) kullanılsaydı toplam 200 bulunurdu.

    def test_extended_policy_does_not_reject_all_buys_without_losses(self):
        start = datetime(2026, 11, 13, tzinfo=timezone.utc)
        bars = [Bar(start+timedelta(hours=i), {'BTCUSDT':100}) for i in range(2)]
        result = run_backtest(bars, Scripted({0:[OrderIntent('BTCUSDT',BUY,quantity=1)]}),
            BacktestConfig(initial_cash=1000, fees=FeeSchedule(0,0),
                risk=RiskLimits(max_daily_realized_loss=50,max_total_position_notional=200,
                                max_price_age=timedelta(seconds=30))))
        self.assertEqual(len(result.trades), 1)
        self.assertEqual(result.rejections, [])
