"""Ödülle öğrenme için sentetik, tek adımlı ve çevrimdışı deney.

Küçük sinir ağı bir eylem seçer; yapay ortam yalnızca +1/-1 ödül döndürür.
Piyasa, Jev, kullanıcı verisi, alım satım veya gerçek para içermez.
"""
import math
import random


class Policy:
    """2 girdi, ReLU gizli katman, eylem 1 olasılığı döndüren sigmoid."""

    def __init__(self, seed=7, hidden=8):
        rng = random.Random(seed)
        self.w = [[rng.uniform(-1, 1), rng.uniform(-1, 1)] for _ in range(hidden)]
        self.b = [0.0] * hidden
        self.v = [rng.uniform(-1, 1) for _ in range(hidden)]
        self.c = 0.0

    def forward(self, x, y):
        raw = [w[0] * x + w[1] * y + b for w, b in zip(self.w, self.b)]
        hidden = [max(0.0, z) for z in raw]
        z = sum(a * b for a, b in zip(self.v, hidden)) + self.c
        p = 1 / (1 + math.exp(-max(-40.0, min(40.0, z))))
        return p, raw, hidden

    def update(self, x, y, action, reward, rate=0.03):
        """REINFORCE: ödül × seçilen eylemin log olasılığının gradyanı."""
        if (type(action) is not int or action not in (0, 1)
                or not math.isfinite(reward) or not math.isfinite(rate) or rate <= 0):
            raise ValueError("Geçersiz eylem, ödül veya öğrenme oranı")
        p, raw, hidden = self.forward(x, y)
        gradient = reward * (action - p)
        old_v = self.v.copy()
        for i in range(len(self.v)):
            self.v[i] += rate * gradient * hidden[i]
            dh = gradient * old_v[i] if raw[i] > 0 else 0.0
            self.w[i][0] += rate * dh * x
            self.w[i][1] += rate * dh * y
            self.b[i] += rate * dh
        self.c += rate * gradient


def reward_for(x, y, action):
    """Gizli sentetik kural: aynı işaret için 1, farklı işaret için 0."""
    correct = int(x * y > 0)
    return 1.0 if action == correct else -1.0


def train(policy, seed=11, episodes=20000):
    """Politikaya doğru cevap değil, yalnızca seçtiği eylemin ödülü verilir."""
    rng = random.Random(seed)
    for _ in range(episodes):
        x, y = rng.uniform(-1, 1), rng.uniform(-1, 1)
        p, _, _ = policy.forward(x, y)
        action = int(rng.random() < p)
        policy.update(x, y, action, reward_for(x, y, action))


def evaluate(policy, seed=900, count=2000):
    """Ayrı tohumla üretilen örneklerde dondurulmuş politikayı değerlendirir."""
    if count < 1:
        raise ValueError("Test örneği sayısı pozitif olmalı")
    rng = random.Random(seed)
    hits = sum(int(reward_for(x, y, int(policy.forward(x, y)[0] >= 0.5)) > 0)
               for x, y in ((rng.uniform(-1, 1), rng.uniform(-1, 1))
                            for _ in range(count)))
    return hits / count


def run_experiment():
    policy = Policy(seed=7)
    before = evaluate(policy, seed=900)
    train(policy, seed=11)
    after = evaluate(policy, seed=901)  # Eğitimde ve model ayarında kullanılmayan veri.
    return {"before": before, "after": after, "random_baseline": 0.5,
            "training_episodes": 20000, "test_points": 2000}


if __name__ == "__main__":
    result = run_experiment()
    print("Sentetik ödülle öğrenme; kripto veya yatırım testi değildir.")
    print(f"Eğitim öncesi: %{result['before'] * 100:.1f}")
    print(f"Ayrı testte eğitim sonrası: %{result['after'] * 100:.1f}")
    print("Rastgele eylem beklenen tabanı: %50")
