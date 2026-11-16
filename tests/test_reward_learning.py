import copy
import unittest

from experiments.reward_learning import Policy, evaluate, reward_for, run_experiment, train


class RewardLearningTests(unittest.TestCase):
    def test_reward_increases_probability_of_selected_action(self):
        for action in (0, 1):
            model = Policy(seed=1)
            before = model.forward(0.4, -0.7)[0]
            model.update(0.4, -0.7, action, 1, rate=0.01)
            after = model.forward(0.4, -0.7)[0]
            self.assertGreater(after, before) if action else self.assertLess(after, before)

    def test_negative_reward_reduces_selected_action_probability(self):
        model = Policy(seed=1)
        before = model.forward(0.4, -0.7)[0]
        model.update(0.4, -0.7, 1, -1, rate=0.01)
        self.assertLess(model.forward(0.4, -0.7)[0], before)

    def test_zero_reward_does_not_change_parameters(self):
        model = Policy(seed=1)
        before = copy.deepcopy((model.w, model.b, model.v, model.c))
        model.update(0.2, 0.7, 1, 0)
        self.assertEqual(before, (model.w, model.b, model.v, model.c))

    def test_reward_and_input_validation(self):
        self.assertEqual(reward_for(1, 1, 1), 1)
        self.assertEqual(reward_for(1, -1, 1), -1)
        with self.assertRaises(ValueError):
            Policy().update(0, 0, 2, 1)
        with self.assertRaises(ValueError):
            Policy().update(0, 0, True, 1)
        with self.assertRaises(ValueError):
            Policy().update(0, 0, 1, 1, rate=float("nan"))
        with self.assertRaises(ValueError):
            evaluate(Policy(), count=0)

    def test_learning_beats_random_on_separate_synthetic_data(self):
        result = run_experiment()
        self.assertGreater(result["after"], result["random_baseline"] + 0.25)
        self.assertGreater(result["after"], result["before"] + 0.15)

    def test_multiple_seeds_generalize_on_new_points(self):
        for seed in range(3):
            with self.subTest(seed=seed):
                model = Policy(seed=100 + seed)
                train(model, seed=200 + seed)
                self.assertGreater(evaluate(model, seed=1000 + seed), 0.8)


if __name__ == "__main__":
    unittest.main()
