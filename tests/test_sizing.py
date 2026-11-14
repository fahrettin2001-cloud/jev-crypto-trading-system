import math
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from jev.backtest import BacktestConfig, run_backtest
from jev.fees import FeeSchedule
from jev.sizing import VolatilityTargetSizer, realized_volatility
from jev.strategy import BUY, Bar, PortfolioView, SmaCross

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parent.parent


def alternating(start, pct, n):
    """Her bar ±pct oynayan fiyat serisi: bilinen oynaklık."""
    out, p = [], start
    for i in range(n):
        out.append(p)
        p = p * (1 + pct) if i % 2 == 0 else p / (1 + pct)
    return out


class RealizedVolatilityTests(unittest.TestCase):
    def test_known_value(self):
        # log getiriler +r, -r, +r, ... ; std = r * sqrt(n/(n-1))
        closes = alternating(100.0, 0.01, 11)
        r = math.log(1.01)
        rets = 10
        expected = r * math.sqrt(rets / (rets - 1)) * math.sqrt(24)
        self.assertAlmostEqual(realized_volatility(closes, 24), expected, places=12)

    def test_constant_prices_zero_and_short_series_none(self):
        self.assertEqual(realized_volatility([5, 5, 5, 5], 24), 0)
        self.assertIsNone(realized_volatility([5, 6], 24))
        with self.assertRaises(ValueError):
            realized_volatility([5, 0, 6], 24)


class SizerTests(unittest.TestCase):
    def feed(self, sizer, closes, symbol="BTCUSDT"):
        for c in closes:
            sizer.observe(symbol, c)

    def test_none_until_window_full(self):
        s = VolatilityTargetSizer("0.02", window=5)
        self.feed(s, [100, 101, 100, 101, 100])
        self.assertIsNone(s.fraction("BTCUSDT"))
        s.observe("BTCUSDT", 101)
        self.assertIsNotNone(s.fraction("BTCUSDT"))
        self.assertIsNone(s.fraction("ETHUSDT"))

    def test_higher_volatility_smaller_fraction(self):
        calm, wild = VolatilityTargetSizer("0.02", 10), VolatilityTargetSizer("0.02", 10)
        self.feed(calm, alternating(100.0, 0.001, 11))
        self.feed(wild, alternating(100.0, 0.01, 11))
        self.assertGreater(calm.fraction("BTCUSDT"), wild.fraction("BTCUSDT"))

    def test_fraction_formula_and_cap(self):
        s = VolatilityTargetSizer("0.02", window=10, max_fraction="0.95")
        self.feed(s, alternating(100.0, 0.01, 11))
        vol = s.volatility("BTCUSDT")  # ~ %5 günlük
        expected = (Decimal("0.02") / Decimal(vol)).quantize(Decimal("0.0001"),
                                                              rounding="ROUND_DOWN")
        self.assertEqual(s.fraction("BTCUSDT"), expected)
        flat = VolatilityTargetSizer("0.02", window=4, max_fraction="0.5")
        self.feed(flat, [100] * 5)
        self.assertEqual(flat.fraction("BTCUSDT"), Decimal("0.5"))

    def test_only_last_window_used(self):
        s = VolatilityTargetSizer("0.02", window=5)
        self.feed(s, alternating(100.0, 0.05, 20) + [100] * 6)
        self.assertEqual(s.volatility("BTCUSDT"), 0)

    def test_validation(self):
        for kwargs in ({"target_daily_vol": "0"}, {"window": 2}, {"bars_per_day": 0},
                       {"max_fraction": "0"}, {"max_fraction": "1.5"}):
            with self.assertRaises(ValueError):
                VolatilityTargetSizer(**kwargs)


class SmaWithSizerTests(unittest.TestCase):
    def bars(self, closes):
        return [Bar(T0 + timedelta(hours=i), {"BTCUSDT": c}) for i, c in enumerate(closes)]

    def series(self, swing):
        # Düşüş, sonra yükseliş (SMA 2/4 yukarı kesişim), üstüne ± salınım
        base = [100 - i for i in range(8)] + [92 + 2 * i for i in range(8)]
        return [Decimal(str(round(b * (1 + (swing if i % 2 else -swing)), 2)))
                for i, b in enumerate(base)]

    def first_buy(self, swing):
        sizer = VolatilityTargetSizer("0.02", window=4, bars_per_day=24)
        strat = SmaCross("BTCUSDT", 2, 4, sizer=sizer)
        for bar in self.bars(self.series(swing)):
            out = strat.on_bar(bar, PortfolioView(Decimal("10000"), equity=Decimal("10000")))
            if out:
                return out[0]
        return None

    def test_buy_size_shrinks_with_volatility(self):
        calm, wild = self.first_buy(0.001), self.first_buy(0.02)
        self.assertEqual((calm.side, wild.side), (BUY, BUY))
        self.assertGreater(calm.quote_amount, wild.quote_amount)
        self.assertIn("oynaklığa göre", wild.reason)

    def test_amount_never_exceeds_cash(self):
        sizer = VolatilityTargetSizer("0.5", window=4, max_fraction="0.95")
        strat = SmaCross("BTCUSDT", 2, 4, sizer=sizer)
        for bar in self.bars(self.series(0.001)):
            out = strat.on_bar(bar, PortfolioView(Decimal("100"), equity=Decimal("10000")))
            if out:
                self.assertLessEqual(out[0].quote_amount, Decimal("100"))
                return
        self.fail("alış önerisi gelmedi")

    def test_no_buy_without_enough_history(self):
        sizer = VolatilityTargetSizer("0.02", window=50)
        strat = SmaCross("BTCUSDT", 2, 4, sizer=sizer)
        outs = [strat.on_bar(b, PortfolioView(Decimal("10000"), equity=Decimal("10000")))
                for b in self.bars(self.series(0.01))]
        self.assertEqual([o for o in outs if o], [])

    def test_backtest_runs_with_sizer(self):
        sizer = VolatilityTargetSizer("0.02", window=4)
        r = run_backtest(self.bars(self.series(0.01)), SmaCross("BTCUSDT", 2, 4, sizer=sizer),
                         BacktestConfig(initial_cash=10000, fees=FeeSchedule("0", "0")))
        self.assertGreaterEqual(r.metrics.buys, 1)
        self.assertGreaterEqual(r.portfolio.cash, 0)

    def test_cli_option(self):
        out = subprocess.run(
            [sys.executable, "-m", "jev.backtest", "--prices",
             "data/synthetic_klines/BTCUSDT-1h-sentetik.csv", "--kline-symbols", "BTCUSDT",
             "--fast", "24", "--slow", "96", "--vol-target", "0.02"],
            cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("oynaklık-hedefi", out.stdout)


if __name__ == "__main__":
    unittest.main()
