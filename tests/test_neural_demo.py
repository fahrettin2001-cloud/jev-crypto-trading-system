import unittest

from experiments.neural_demo import TinyNetwork, accuracy, make_data, run_demo


class NeuralDemoTests(unittest.TestCase):
    def test_labels_and_determinism(self):
        data = make_data(25, seed=42)
        self.assertEqual(data, make_data(25, seed=42))
        self.assertTrue(all(label == int(x * y > 0) for x, y, label in data))
        self.assertNotEqual(data, make_data(25, seed=43))

    def test_model_learns_synthetic_task(self):
        result = run_demo()
        self.assertGreater(result["after"], result["before"])
        self.assertGreater(result["after"], result["baseline"] + 0.15)

    def test_invalid_empty_data(self):
        model = TinyNetwork()
        with self.assertRaises(ValueError):
            model.train_step([])
        with self.assertRaises(ValueError):
            accuracy(model, [])


if __name__ == "__main__":
    unittest.main()
