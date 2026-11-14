import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from experiments.market_research import Price
from experiments.walk_forward import make_windows, run_walk_forward


class WalkForwardTests(unittest.TestCase):
    def setUp(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.prices = [Price(start + timedelta(hours=i), Decimal(100 + i % 11))
                       for i in range(200)]

    def test_windows_are_ordered_purged_and_reserved_not_used(self):
        windows, reserved = make_windows(self.prices, lookback=6, horizon=3)
        self.assertEqual((len(windows), reserved), (4, 160))
        seen = set()
        for train, evaluation in windows:
            self.assertLess(train[-1].target_index, evaluation[0].index)
            self.assertLess(evaluation[-1].target_index, reserved)
            indices = {e.index for e in evaluation}
            self.assertFalse(seen & indices)
            seen.update(indices)

    def test_future_and_holdout_changes_cannot_change_earlier_windows(self):
        before, reserved = make_windows(self.prices)
        split = before[0][1][0].index
        mutated = [p if i < split else Price(p.time, p.close * 2)
                   for i, p in enumerate(self.prices)]
        after, _ = make_windows(mutated)
        self.assertEqual(before[0][0], after[0][0])
        holdout_changed = [p if i < reserved else Price(p.time, p.close * 3)
                           for i, p in enumerate(self.prices)]
        self.assertEqual(before, make_windows(holdout_changed)[0])

    def test_prediction_scores_share_exact_evaluation_count(self):
        result = run_walk_forward(self.prices)
        self.assertFalse(result['reserved_evaluated'])
        self.assertEqual(result['reserved_bars'], 40)
        for window in result['windows']:
            self.assertLess(window['last_train_target'], window['eval_first'])
            expected = window['neural']['count']
            for name in ('logistic', 'train_prevalence', 'constant_half'):
                self.assertEqual(expected, window[name]['count'])
            self.assertEqual(window['constant_half']['brier'], 0.25)

    def test_bad_inputs_and_data_gap_fail(self):
        with self.assertRaises(ValueError):
            make_windows(self.prices[:20], horizon=5)
        with self.assertRaises(ValueError):
            make_windows(self.prices, horizon=True)
        with self.assertRaises(ValueError):
            make_windows(self.prices[:40] + self.prices[41:])


if __name__ == '__main__':
    unittest.main()
