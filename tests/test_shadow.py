import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from jev.shadow import brier_score, replay
from jev.strategy import Bar


class ShadowTests(unittest.TestCase):
    def setUp(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.bars = [Bar(start + timedelta(hours=i), {"BTCUSDT": Decimal(p)})
                     for i, p in enumerate(("100", "110", "110", "99"))]

    def test_predictor_only_receives_history_and_horizon_is_exact(self):
        seen = []
        def predict(history, symbol, horizon):
            seen.append((len(history), history[-1].timestamp, symbol, horizon))
            return Decimal("0.8")
        result = replay(self.bars, "BTCUSDT", 2, predict)
        self.assertEqual([x[0] for x in seen], [1, 2, 3, 4])
        self.assertEqual([r.increased for r in result], [True, False, None, None])
        self.assertEqual(result[0].outcome_time, self.bars[2].timestamp)
        self.assertEqual(brier_score(result), Decimal("0.34"))

    def test_invalid_input_fails_before_predicting(self):
        for bars, symbol, horizon in [(self.bars[::-1], "BTCUSDT", 1),
                                      (self.bars, "ETHUSDT", 1),
                                      (self.bars, "BTCUSDT", True)]:
            with self.subTest(symbol=symbol, horizon=horizon):
                with self.assertRaises(ValueError):
                    replay(bars, symbol, horizon, lambda *args: self.fail("unexpected call"))

    def test_invalid_probability_and_unresolved_forecast(self):
        for value in ("NaN", "-0.1", "1.1"):
            with self.assertRaises(ValueError):
                replay(self.bars, "BTCUSDT", 1, lambda *args: value)
        result = replay(self.bars[:1], "BTCUSDT", 1, lambda *args: "0.5")
        self.assertIsNone(brier_score(result))


if __name__ == "__main__":
    unittest.main()
