import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from experiments.market_research import Price, build_splits, load_prices, research, train_model


class MarketResearchTests(unittest.TestCase):
    def setUp(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.prices = [Price(start + timedelta(hours=i), Decimal(100 + i % 9))
                       for i in range(100)]

    def test_labels_do_not_cross_section_boundaries(self):
        parts = build_splits(self.prices, lookback=6, horizon=3,
                             train_end=60, validation_end=80)
        self.assertTrue(all(e.index < 60 and e.target_index < 60 for e in parts['train']))
        self.assertTrue(all(60 <= e.index < 80 and e.target_index < 80
                            for e in parts['validation']))
        self.assertTrue(all(e.index >= 80 and e.target_index < 100 for e in parts['test']))
        self.assertEqual(parts['train'][-1].index, 56)
        self.assertEqual(parts['validation'][0].index, 60)
        self.assertEqual(parts['validation'][-1].index, 76)

    def test_future_changes_label_not_current_features(self):
        original = build_splits(self.prices, lookback=6, horizon=3,
                                train_end=60, validation_end=80)['train'][4]
        changed = self.prices.copy()
        j = original.target_index
        changed[j] = Price(changed[j].time, self.prices[original.index].close / Decimal('2'))
        modified = build_splits(changed, lookback=6, horizon=3,
                                train_end=60, validation_end=80)['train'][4]
        self.assertEqual(original.features, modified.features)
        self.assertEqual(modified.label, 0)
        self.assertNotEqual(original.label, modified.label)

    def test_training_unchanged_by_validation_and_test_prices(self):
        def weights(prices):
            return train_model(build_splits(prices, lookback=6, horizon=3,
                                            train_end=60, validation_end=80)['train'])
        changed = [p if i < 60 else Price(p.time, p.close * 2)
                   for i, p in enumerate(self.prices)]
        self.assertEqual(weights(self.prices), weights(changed))

    def test_data_gaps_duplicates_naive_timestamps_and_invalid_prices_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'prices.csv'
            def check(rows):
                with path.open('w', newline='', encoding='utf-8') as stream:
                    writer = csv.writer(stream)
                    writer.writerow(('timestamp', 'symbol', 'close'))
                    writer.writerows(rows)
                return load_prices(path, 'BTCUSDT', timedelta(hours=1))
            valid = [('2026-01-01T00:00:00+00:00', 'BTCUSDT', '100'),
                     ('2026-01-01T01:00:00+00:00', 'BTCUSDT', '101')]
            self.assertEqual(len(check(valid)), 2)
            for rows in (valid[:1] * 2, [valid[1], valid[0]],
                         [valid[0], ('2026-01-01T02:00:00+00:00', 'BTCUSDT', '101')],
                         [('2026-01-01T00:00:00', 'BTCUSDT', '100')],
                         [('2026-01-01T00:00:00+00:00', 'BTCUSDT', 'NaN')]):
                with self.subTest(rows=rows), self.assertRaises(ValueError):
                    check(rows)

    def test_reports_have_comparable_counts_and_are_repeatable(self):
        report = research(self.prices)
        self.assertEqual(report, research(self.prices))
        for section in report['sections'].values():
            self.assertEqual(section['logistic']['count'], section['majority_from_train']['count'])
            self.assertEqual(section['constant_half']['brier'], 0.25)

    def test_equal_future_price_is_not_an_increase(self):
        flat = [Price(p.time, Decimal('100')) for p in self.prices]
        parts = build_splits(flat, lookback=6, horizon=3, train_end=60, validation_end=80)
        self.assertTrue(all(e.label == 0 for group in parts.values() for e in group))

    def test_no_complete_split_rejected(self):
        with self.assertRaises(ValueError):
            research(self.prices[:12], lookback=6, horizon=3)

    def test_in_memory_series_also_rejects_gap_and_duplicate(self):
        for bad in (self.prices[:20] + self.prices[21:],
                    self.prices[:20] + [self.prices[19]] + self.prices[20:]):
            with self.subTest(size=len(bad)), self.assertRaises(ValueError):
                build_splits(bad, lookback=6, horizon=3, train_end=55, validation_end=75)


if __name__ == '__main__':
    unittest.main()
