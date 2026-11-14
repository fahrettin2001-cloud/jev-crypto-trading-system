import unittest
from decimal import Decimal

from jev.exchange_rules import ExchangeRuleError, ExchangeRules, SymbolRules


def btc_rules(**overrides):
    base = dict(symbol="BTCUSDT", base_asset="BTC", quote_asset="USDT",
                min_price="0.01", max_price="1000000", tick_size="0.01",
                min_qty="0.00001", max_qty="9000", step_size="0.00001",
                min_notional="5")
    base.update(overrides)
    return SymbolRules(**base)


class SymbolRulesTests(unittest.TestCase):
    def test_valid_market_order_passes(self):
        btc_rules().check("0.001", "60000")

    def test_quantity_not_multiple_of_step_rejected(self):
        with self.assertRaisesRegex(ExchangeRuleError, "LOT_SIZE"):
            btc_rules().check("0.000015", "60000")

    def test_quantity_below_min_rejected(self):
        with self.assertRaisesRegex(ExchangeRuleError, "asgari"):
            btc_rules().check("0.000001", "60000")

    def test_quantity_above_max_rejected(self):
        with self.assertRaisesRegex(ExchangeRuleError, "azami"):
            btc_rules().check("9001", "1")

    def test_min_notional_rejected(self):
        # 0.00008 BTC * 60000 = 4.8 USDT < 5
        with self.assertRaisesRegex(ExchangeRuleError, "NOTIONAL"):
            btc_rules().check("0.00008", "60000")

    def test_min_notional_not_applied_to_market_when_disabled(self):
        btc_rules(apply_min_to_market=False).check("0.00008", "60000")

    def test_price_filter_only_for_limit_orders(self):
        rules = btc_rules()
        rules.check("0.001", "60000.005")  # piyasa emri: fiyat filtresi yok
        with self.assertRaisesRegex(ExchangeRuleError, "PRICE_FILTER"):
            rules.check("0.001", "60000.005", market=False)

    def test_not_trading_rejected(self):
        with self.assertRaisesRegex(ExchangeRuleError, "işleme açık değil"):
            btc_rules(status="BREAK").check("0.001", "60000")

    def test_floor_quantity_never_rounds_up(self):
        rules = btc_rules()
        self.assertEqual(rules.floor_quantity("0.123456789"), Decimal("0.12345"))
        self.assertEqual(rules.floor_quantity("0.000019"), Decimal("0.00001"))
        self.assertEqual(rules.floor_quantity("0.000009"), Decimal("0"))

    def test_floored_quantity_always_passes_lot_size(self):
        rules = btc_rules()
        for raw in ("0.0123456", "1.999999", "0.0001", "3.3333333"):
            q = rules.floor_quantity(raw)
            rules.check(q, "60000")
            self.assertLessEqual(q, Decimal(raw))

    def test_round_price(self):
        rules = btc_rules()
        self.assertEqual(rules.round_price("60000.019"), Decimal("60000.01"))
        self.assertEqual(rules.round_price("60000.011", up=True), Decimal("60000.02"))

    def test_zero_disables_rule(self):
        SymbolRules("X", "A", "B").check("0.123456789", "0.0000001")

    def test_negative_rule_value_rejected(self):
        with self.assertRaises(ValueError):
            btc_rules(step_size="-1")


class ExchangeInfoParsingTests(unittest.TestCase):
    def test_sample_file_parses(self):
        rules = ExchangeRules.load()
        self.assertEqual(rules.symbols(), ["BTCUSDT", "ETHUSDT"])
        btc = rules["BTCUSDT"]
        self.assertEqual(btc.step_size, Decimal("0.00001"))
        self.assertEqual(btc.min_notional, Decimal("5"))
        self.assertTrue(btc.apply_min_to_market)

    def test_unknown_symbol(self):
        with self.assertRaises(ExchangeRuleError):
            ExchangeRules.load()["DOGEUSDT"]

    def test_legacy_min_notional_filter(self):
        info = {"symbols": [{"symbol": "X", "baseAsset": "A", "quoteAsset": "B", "filters": [
            {"filterType": "MIN_NOTIONAL", "minNotional": "10", "applyToMarket": False}]}]}
        x = ExchangeRules.from_exchange_info(info)["X"]
        self.assertEqual(x.min_notional, Decimal("10"))
        self.assertFalse(x.apply_min_to_market)

    def test_market_lot_size_applies_to_market_orders(self):
        info = {"symbols": [{"symbol": "X", "baseAsset": "A", "quoteAsset": "B", "filters": [
            {"filterType": "LOT_SIZE", "minQty": "0.001", "maxQty": "1000", "stepSize": "0.001"},
            {"filterType": "MARKET_LOT_SIZE", "minQty": "0", "maxQty": "10", "stepSize": "0"}]}]}
        x = ExchangeRules.from_exchange_info(info)["X"]
        x.check("50", "1", market=False)
        with self.assertRaisesRegex(ExchangeRuleError, "MARKET_LOT_SIZE"):
            x.check("50", "1", market=True)

    def test_empty_response_rejected(self):
        with self.assertRaises(ValueError):
            ExchangeRules.from_exchange_info({"symbols": []})


if __name__ == "__main__":
    unittest.main()
