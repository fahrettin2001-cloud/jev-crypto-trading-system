import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from experiments.market_neural import compare, fit_neural, fit_scaler, transform
from experiments.market_research import Price, build_splits


class MarketNeuralTests(unittest.TestCase):
    def setUp(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.prices = [Price(start + timedelta(hours=i), Decimal(100 + i % 9))
                       for i in range(100)]

    def training(self, prices):
        return build_splits(prices, lookback=6, horizon=3,
                            train_end=60, validation_end=80)['train']

    def test_future_prices_cannot_change_training_or_normalization(self):
        changed = [p if i < 60 else Price(p.time, p.close * 2)
                   for i, p in enumerate(self.prices)]
        first, second = self.training(self.prices), self.training(changed)
        self.assertEqual(fit_scaler(first), fit_scaler(second))
        model_a, mean_a, scale_a = fit_neural(first)
        model_b, mean_b, scale_b = fit_neural(second)
        self.assertEqual((mean_a, scale_a), (mean_b, scale_b))
        self.assertEqual((model_a.weights, model_a.biases, model_a.output_weights, model_a.output_bias),
                         (model_b.weights, model_b.biases, model_b.output_weights, model_b.output_bias))

    def test_constant_training_features_do_not_divide_by_zero(self):
        flat = [Price(p.time, Decimal('100')) for p in self.prices]
        means, scales = fit_scaler(self.training(flat))
        self.assertEqual((means, scales), ((0.0, 0.0), (1.0, 1.0)))
        self.assertEqual(transform((0.0, 0.0), means, scales), (0.0, 0.0))

    def test_same_splits_repeatable_and_probabilities_valid(self):
        a = compare(self.prices)
        b = compare(self.prices)
        self.assertEqual(a, b)
        for section in a['sections'].values():
            self.assertEqual(section['neural']['count'], section['logistic']['count'])
            self.assertGreaterEqual(section['neural']['brier'], 0)
            self.assertLessEqual(section['neural']['brier'], 1)

    def test_missing_training_rejected(self):
        with self.assertRaises(ValueError):
            fit_scaler([])


if __name__ == '__main__':
    unittest.main()
