import unittest
from decimal import Decimal

from jev import FeeSchedule, Portfolio, TradeError


class PortfolioTests(unittest.TestCase):
    def setUp(self):
        self.p = Portfolio(cash=10000, fees=FeeSchedule(taker_rate="0.001"))

    def test_buy_deducts_cost_and_fee(self):
        t = self.p.buy("BTCUSDT", "0.1", 50000)  # 5000 + 5 komisyon
        self.assertEqual(t.fee, Decimal("5"))
        self.assertEqual(self.p.cash, Decimal("4995"))
        pos = self.p.positions["BTCUSDT"]
        self.assertEqual(pos.quantity, Decimal("0.1"))
        self.assertEqual(pos.avg_cost, Decimal("50050"))  # komisyon dahil

    def test_average_cost_over_two_buys(self):
        fees = FeeSchedule(taker_rate="0")
        p = Portfolio(cash=10000, fees=fees)
        p.buy("ETHUSDT", 1, 2000)
        p.buy("ETHUSDT", 1, 3000)
        self.assertEqual(p.positions["ETHUSDT"].avg_cost, Decimal("2500"))

    def test_round_trip_at_same_price_loses_exactly_fees(self):
        self.p.buy("BTCUSDT", "0.1", 50000)
        t = self.p.sell("BTCUSDT", "0.1", 50000)
        self.assertEqual(self.p.total_fees, Decimal("10"))
        self.assertEqual(self.p.cash, Decimal("9990"))
        self.assertEqual(t.realized_pnl, Decimal("-10"))
        self.assertNotIn("BTCUSDT", self.p.positions)

    def test_profitable_sell(self):
        self.p.buy("BTCUSDT", "0.1", 50000)          # maliyet 5005
        t = self.p.sell("BTCUSDT", "0.1", 60000)     # gelir 6000 - 6
        self.assertEqual(t.realized_pnl, Decimal("989"))
        self.assertEqual(self.p.realized_pnl, Decimal("989"))
        self.assertEqual(self.p.cash, Decimal("10989"))

    def test_partial_sell_keeps_avg_cost(self):
        self.p.buy("BTCUSDT", "0.1", 50000)
        self.p.sell("BTCUSDT", "0.04", 55000)
        pos = self.p.positions["BTCUSDT"]
        self.assertEqual(pos.quantity, Decimal("0.06"))
        self.assertEqual(pos.avg_cost, Decimal("50050"))

    def test_equity_and_unrealized_pnl(self):
        self.p.buy("BTCUSDT", "0.1", 50000)
        prices = {"BTCUSDT": Decimal("52000")}
        self.assertEqual(self.p.market_value(prices), Decimal("5200"))
        self.assertEqual(self.p.equity(prices), Decimal("10195"))
        self.assertEqual(self.p.unrealized_pnl(prices), Decimal("195"))

    def test_insufficient_cash_rejected_without_side_effects(self):
        with self.assertRaises(TradeError):
            self.p.buy("BTCUSDT", 1, 10000)  # 10000 + 10 komisyon > 10000
        self.assertEqual(self.p.cash, Decimal("10000"))
        self.assertEqual(self.p.positions, {})
        self.assertEqual(self.p.trades, [])

    def test_oversell_and_short_rejected(self):
        with self.assertRaises(TradeError):
            self.p.sell("ETHUSDT", 1, 3000)
        self.p.buy("ETHUSDT", 1, 3000)
        with self.assertRaises(TradeError):
            self.p.sell("ETHUSDT", 2, 3000)

    def test_invalid_quantity_or_price(self):
        for qty, price in ((0, 100), (-1, 100), (1, 0), (1, -5)):
            with self.assertRaises(TradeError):
                self.p.buy("BTCUSDT", qty, price)

    def test_missing_price_raises(self):
        self.p.buy("BTCUSDT", "0.01", 50000)
        with self.assertRaises(KeyError):
            self.p.equity({})

    def test_negative_initial_cash_rejected(self):
        with self.assertRaises(ValueError):
            Portfolio(cash=-1)

    def test_trade_history_recorded(self):
        self.p.buy("BTCUSDT", "0.1", 50000)
        self.p.sell("BTCUSDT", "0.05", 51000)
        self.assertEqual([t.side for t in self.p.trades], ["BUY", "SELL"])


if __name__ == "__main__":
    unittest.main()
