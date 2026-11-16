import unittest
from datetime import date, timedelta

from experiments.ajan_kurulu_pilot.puanla import CASES, evaluate, validate_forecasts


def forecasts():
    return {"episodes": [{"id": key, "bull": 0.4, "bear": 0.5, "risk": 0.6} for key in CASES]}


class PilotTests(unittest.TestCase):
    def test_missing_duplicate_nan_and_boolean_are_rejected(self):
        for mode in ("missing", "duplicate", "nan", "boolean"):
            data = forecasts()
            if mode == "missing":
                data["episodes"].pop()
            elif mode == "duplicate":
                data["episodes"][-1]["id"] = data["episodes"][0]["id"]
            else:
                data["episodes"][0]["bull"] = float("nan") if mode == "nan" else True
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                validate_forecasts(data)

    def test_target_uses_twentieth_day_and_scores_half(self):
        prices = {s: {} for s in ("BTCUSDT", "ETHUSDT")}
        for _, (symbol, text) in CASES.items():
            day = date.fromisoformat(text)
            prices[symbol][day] = 100
            prices[symbol][day + timedelta(days=19)] = 1
            prices[symbol][day + timedelta(days=20)] = 101
        result = evaluate(forecasts(), prices)
        self.assertEqual(result["count"], 6)
        self.assertEqual(result["mean_brier"], 0.25)
        self.assertTrue(all(row["actual_up"] == 1 for row in result["forecasts"]))


if __name__ == "__main__":
    unittest.main()
