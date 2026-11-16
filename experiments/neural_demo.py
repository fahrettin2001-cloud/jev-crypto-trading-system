"""Görev 6: sentetik XOR verisiyle küçük, çevrimdışı sinir ağı deneyi.

Bu eğitim örneği piyasa tahmini, Jev, ödül öğrenmesi veya işlem sistemi değildir.
Yalnızca Python standart kütüphanesini kullanır.
"""
import math
import random


def make_data(count, seed):
    """İki koordinatı aynı işarette olan noktaları 1, diğerlerini 0 etiketle."""
    rng = random.Random(seed)
    points = [(rng.uniform(-1, 1), rng.uniform(-1, 1)) for _ in range(count)]
    return [(x, y, int(x * y > 0)) for x, y in points]


class TinyNetwork:
    """2 girdi, 8 ReLU nöronu ve sigmoid çıktılı sınıflandırıcı."""

    def __init__(self, seed=7, hidden=8):
        rng = random.Random(seed)
        self.weights = [[rng.uniform(-1, 1), rng.uniform(-1, 1)] for _ in range(hidden)]
        self.biases = [0.0] * hidden
        self.output_weights = [rng.uniform(-1, 1) for _ in range(hidden)]
        self.output_bias = 0.0

    def predict(self, x, y):
        hidden = [max(0.0, w[0] * x + w[1] * y + b)
                  for w, b in zip(self.weights, self.biases)]
        z = sum(v * h for v, h in zip(self.output_weights, hidden)) + self.output_bias
        # Sayısal taşmaları önle; sonuç 0 ile 1 arasındadır.
        return 1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, z))))

    def train_step(self, batch, rate=0.1):
        if not batch:
            raise ValueError("Eğitim kümesi boş olamaz")
        count = len(self.weights)
        dw = [[0.0, 0.0] for _ in range(count)]
        db = [0.0] * count
        dv = [0.0] * count
        dc = 0.0
        for x, y, label in batch:
            raw = [w[0] * x + w[1] * y + b for w, b in zip(self.weights, self.biases)]
            hidden = [max(0.0, z) for z in raw]
            error = self.predict(x, y) - label  # sigmoid + çapraz entropi türevi
            dc += error
            for i in range(count):
                dv[i] += error * hidden[i]
                grad = error * self.output_weights[i] if raw[i] > 0 else 0.0
                dw[i][0] += grad * x
                dw[i][1] += grad * y
                db[i] += grad
        scale = rate / len(batch)
        for i in range(count):
            self.weights[i][0] -= scale * dw[i][0]
            self.weights[i][1] -= scale * dw[i][1]
            self.biases[i] -= scale * db[i]
            self.output_weights[i] -= scale * dv[i]
        self.output_bias -= scale * dc


def accuracy(model, data):
    if not data:
        raise ValueError("Test kümesi boş olamaz")
    return sum((model.predict(x, y) >= 0.5) == bool(label)
               for x, y, label in data) / len(data)


def run_demo():
    train = make_data(800, seed=1)
    test = make_data(400, seed=2)  # Eğitimde ve parametre seçiminde kullanılmaz.
    model = TinyNetwork(seed=7)
    before = accuracy(model, test)
    rng = random.Random(3)
    for _ in range(1500):
        model.train_step([train[rng.randrange(len(train))] for _ in range(32)])
    after = accuracy(model, test)
    positive = sum(label for _, _, label in train)
    majority = int(positive >= len(train) / 2)
    baseline = sum(label == majority for _, _, label in test) / len(test)
    return {"before": before, "after": after, "baseline": baseline,
            "training_points": len(train), "test_points": len(test)}


if __name__ == "__main__":
    result = run_demo()
    print("Sentetik sınıflandırma deneyi — yatırım veya piyasa tahmini değildir")
    print(f"Eğitim örneği: {result['training_points']}; test örneği: {result['test_points']}")
    print(f"Eğitim öncesi test doğruluğu: %{result['before'] * 100:.1f}")
    print(f"Eğitim sonrası test doğruluğu: %{result['after'] * 100:.1f}")
    print(f"Eğitimdeki çoğunluk sınıfı tabanı: %{result['baseline'] * 100:.1f}")
