import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from experiments.market_research import Price
from experiments.trend_neural_backtest import simulate


class TrendNeuralBacktestTests(unittest.TestCase):
    def setUp(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.prices = {symbol: [Price(start + timedelta(days=i), Decimal(100 + i * 2))
                                for i in range(6)] for symbol in ("BTC", "ETH")}
        self.signals = {symbol: [(1.0, 1.0)] * 6 for symbol in self.prices}

    def test_filter_always_open_matches_unfiltered(self):
        args = (self.prices, self.signals, "2024-01-02", "2024-01-06")
        self.assertEqual(simulate(*args, False), simulate(*args, True))

    def test_filter_closed_never_trades_and_costs_reduce_result(self):
        closed = {s: [(1.0, 0.1)] * 6 for s in self.prices}
        args = (self.prices, closed, "2024-01-02", "2024-01-06")
        self.assertEqual(simulate(*args, True)["final"], 500.0)
        self.assertEqual(simulate(*args, True)["trades"], 0)
        self.assertGreater(simulate(*args, False, cost=0)["final"], simulate(*args, False)["final"])

    def test_only_previous_day_signal_controls_today(self):
        signal = {s: [(0.0, 1.0), (1.0, 1.0)] + [(0.0, 1.0)] * 4 for s in self.prices}
        first = simulate(self.prices, signal, "2024-01-02", "2024-01-02", False)
        second = simulate(self.prices, signal, "2024-01-03", "2024-01-03", False)
        self.assertEqual(first["trades"], 0)
        self.assertEqual(second["trades"], 2)


if __name__ == "__main__":
    unittest.main()
