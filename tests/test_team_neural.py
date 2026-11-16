import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from experiments.market_research import Price
from experiments.team_neural import build_examples


class TeamNeuralTests(unittest.TestCase):
    def setUp(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        self.prices = [Price(start + timedelta(days=i), Decimal(100 + i % 31))
                       for i in range(2900)]

    def test_same_examples_and_targets_stay_in_sections(self):
        original = build_examples(self.prices, "original")
        team = build_examples(self.prices, "team")
        ends = {"train": "2022-12-31", "validation": "2023-12-31", "test": "2026-10-31"}
        for name in ends:
            self.assertEqual([(e.index, e.label) for e in original[name]],
                             [(e.index, e.label) for e in team[name]])
            self.assertTrue(all(e.target_time.date().isoformat() <= ends[name] for e in team[name]))

    def test_future_test_values_cannot_change_training_or_validation(self):
        before = build_examples(self.prices, "team")
        changed = [Price(p.time, p.close * 2) if p.time.year >= 2024 else p for p in self.prices]
        after = build_examples(changed, "team")
        self.assertEqual(before["train"], after["train"])
        self.assertEqual(before["validation"], after["validation"])


if __name__ == "__main__":
    unittest.main()
