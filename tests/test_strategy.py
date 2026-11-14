import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from jev.strategy import BUY, SELL, Bar, BuyAndHold, OrderIntent, PortfolioView, SmaCross

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def bars(prices, symbol="BTCUSDT"):
    return [Bar(T0 + timedelta(hours=i), {symbol: p}) for i, p in enumerate(prices)]


class OrderIntentTests(unittest.TestCase):
    def test_exactly_one_size_field(self):
        with self.assertRaises(ValueError):
            OrderIntent("BTCUSDT", BUY)
        with self.assertRaises(ValueError):
            OrderIntent("BTCUSDT", BUY, quantity=1, quote_amount=100)

    def test_quote_amount_only_for_buy(self):
        with self.assertRaises(ValueError):
            OrderIntent("BTCUSDT", SELL, quote_amount=100)

    def test_all_only_for_sell(self):
        OrderIntent("BTCUSDT", SELL, quantity="ALL")
        with self.assertRaises(ValueError):
            OrderIntent("BTCUSDT", BUY, quantity="ALL")

    def test_invalid_values(self):
        for kwargs in ({"quantity": 0}, {"quantity": "-1"}, {"quantity": "NaN"},
                       {"quote_amount": 0}):
            with self.assertRaises(ValueError):
                OrderIntent("BTCUSDT", BUY, **kwargs)
        with self.assertRaises(ValueError):
            OrderIntent("BTCUSDT", BUY, quantity=1, confidence="1.5")
        with self.assertRaises(ValueError):
            OrderIntent("BTCUSDT", "HOLD", quantity=1)


class ViewAndBarTests(unittest.TestCase):
    def test_view_is_read_only(self):
        view = PortfolioView(Decimal("100"), {"BTCUSDT": Decimal("1")})
        with self.assertRaises(TypeError):
            view.positions["BTCUSDT"] = Decimal("5")
        self.assertEqual(view.quantity("ETHUSDT"), 0)

    def test_bar_rejects_bad_price_and_is_read_only(self):
        with self.assertRaises(ValueError):
            Bar(T0, {"BTCUSDT": "0"})
        bar = Bar(T0, {"BTCUSDT": "1"})
        with self.assertRaises(TypeError):
            bar.prices["BTCUSDT"] = Decimal("2")


class StrategyTests(unittest.TestCase):
    def run_strategy(self, strategy, series, holding=Decimal("0")):
        out = []
        for bar in bars(series):
            view = PortfolioView(Decimal("1000"), {"BTCUSDT": holding} if holding else {})
            for intent in strategy.on_bar(bar, view):
                out.append((bar.timestamp, intent))
                holding = Decimal("1") if intent.side == BUY else Decimal("0")
        return out

    def test_buy_and_hold_buys_once(self):
        out = self.run_strategy(BuyAndHold("BTCUSDT", "0.5"), [10, 11, 12])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][1].quote_amount, Decimal("500"))

    def test_sma_cross_buys_on_up_cross_and_sells_on_down_cross(self):
        # Düşüş, sonra yükseliş (yukarı kesişim), sonra düşüş (aşağı kesişim)
        series = [10, 9, 8, 7, 6, 7, 9, 12, 15, 14, 11, 8, 5, 4]
        out = self.run_strategy(SmaCross("BTCUSDT", fast=2, slow=4), series)
        sides = [i.side for _, i in out]
        self.assertEqual(sides, [BUY, SELL])
        self.assertLess(out[0][0], out[1][0])

    def test_sma_needs_full_window(self):
        out = self.run_strategy(SmaCross("BTCUSDT", fast=2, slow=5), [1, 2, 3, 4])
        self.assertEqual(out, [])

    def test_sma_does_not_sell_without_position(self):
        series = [10, 11, 12, 13, 14, 13, 10, 7, 5]
        strategy = SmaCross("BTCUSDT", fast=2, slow=4)
        for bar in bars(series):
            self.assertEqual(
                [i for i in strategy.on_bar(bar, PortfolioView(Decimal("0"))) if i.side == SELL], [])

    def test_sma_invalid_windows(self):
        for fast, slow in ((5, 5), (0, 3), (6, 3)):
            with self.assertRaises(ValueError):
                SmaCross("BTCUSDT", fast=fast, slow=slow)


if __name__ == "__main__":
    unittest.main()
