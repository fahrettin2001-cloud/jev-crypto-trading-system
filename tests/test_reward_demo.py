import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from experiments.reward_demo import append_record, reward_record


class RewardDemoTests(unittest.TestCase):
    def test_net_value_includes_fee_once(self):
        record = reward_record("500", "502", "500", period_fees="0.2")
        self.assertEqual(Decimal(record["net_change"]), Decimal("2"))
        self.assertEqual(Decimal(record["reward"]), Decimal("0.004"))

    def test_risk_penalty_only_when_drawdown_increases(self):
        r = reward_record("500", "450", "500", drawdown_weight="0.5")
        self.assertEqual(Decimal(r["risk_penalty"]), Decimal("0.05"))
        self.assertEqual(Decimal(r["reward"]), Decimal("-0.15"))
        r = reward_record("450", "475", "500", drawdown_weight="0.5")
        self.assertEqual(Decimal(r["risk_penalty"]), Decimal("0"))

    def test_invalid_values_rejected(self):
        for args in [(0, 1, 1), (1, -1, 1), (2, 1, 1), (1, "NaN", 1), (True, 1, 1)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                reward_record(*args)
        with self.assertRaises(ValueError):
            reward_record(1, 1, 1, period_fees=-1)
        with self.assertRaises(ValueError):
            reward_record(1, 1, 1, drawdown_weight=-1)

    def test_append_two_distinct_records(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "rewards.jsonl"
            first = reward_record(500, 502, 500)
            second = reward_record(502, 501, 502)
            append_record(path, first)
            append_record(path, second)
            self.assertEqual([json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()],
                             [first, second])


if __name__ == "__main__":
    unittest.main()
