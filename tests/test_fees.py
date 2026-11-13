import unittest
from decimal import Decimal

from jev.fees import D, FeeSchedule


class FeeScheduleTests(unittest.TestCase):
    def test_default_rate_is_0_1_percent(self):
        self.assertEqual(FeeSchedule().fee(1000), Decimal("1.000"))

    def test_maker_and_taker_rates_differ(self):
        fees = FeeSchedule(maker_rate="0.0002", taker_rate="0.0004")
        self.assertEqual(fees.fee(10000, taker=False), Decimal("2"))
        self.assertEqual(fees.fee(10000, taker=True), Decimal("4"))

    def test_float_input_has_no_binary_error(self):
        self.assertEqual(D(0.1), Decimal("0.1"))
        self.assertEqual(FeeSchedule(taker_rate=0.001).fee(0.3), Decimal("0.0003"))

    def test_invalid_rates_rejected(self):
        for bad in ("-0.01", "1", "1.5"):
            with self.assertRaises(ValueError):
                FeeSchedule(taker_rate=bad)

    def test_negative_notional_rejected(self):
        with self.assertRaises(ValueError):
            FeeSchedule().fee(-1)


if __name__ == "__main__":
    unittest.main()
