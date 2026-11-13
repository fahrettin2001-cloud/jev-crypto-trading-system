import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from jev import load_prices


class PriceLoaderTests(unittest.TestCase):
    def test_sample_file_loads_sorted(self):
        rows = load_prices()
        self.assertGreater(len(rows), 0)
        times = [ts for ts, _ in rows]
        self.assertEqual(times, sorted(times))
        self.assertEqual(rows[0][1]["BTCUSDT"], Decimal("60000"))
        self.assertIn("ETHUSDT", rows[0][1])

    def test_invalid_price_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.csv"
            path.write_text("timestamp,symbol,close\n2026-01-01T00:00:00+00:00,BTCUSDT,0\n")
            with self.assertRaises(ValueError):
                load_prices(path)


if __name__ == "__main__":
    unittest.main()
