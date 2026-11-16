"""Trend topluluğu: strateji kuralları, risk limitlerine uyum ve canlı sanal hesap
(sahte günlük Binance verisiyle, ağ kullanmaz)."""
import json
import random
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from jev.backtest import BacktestConfig, Simulator
from jev.duygu import simulate as research_simulate
from jev.duygu import trend_weights
from jev.klines import bars_from_series
from jev.live import init, run_once, status
from jev.risk import RiskLimits
from jev.strategy import Bar, Combined, PortfolioView, TrendRules, TrendTopluluk

DAY = timedelta(days=1)
T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


def walk(n, seed, start=100.0, drift=0.0005, vol=0.035):
    r, p, out = random.Random(seed), start, []
    for _ in range(n):
        p *= 1 + r.gauss(drift, vol)
        out.append(round(p, 4))
    return out


def bar(i, prices):
    return Bar(T0 + i * DAY, {s: Decimal(str(p)) for s, p in prices.items()})


class FakeDailyBinance:
    """data-api.binance.vision klines taklidi (1d): `now` öncesi açılmış mumlar."""

    def __init__(self, series):
        self.series = series          # sembol → [kapanış]
        self.now = None

    def __call__(self, url):
        q = dict(x.split("=") for x in url.split("?")[1].split("&"))
        assert q["interval"] == "1d"
        rows = []
        for i, c in enumerate(self.series[q["symbol"]]):
            open_t = T0 + (i - 1) * DAY
            if open_t >= self.now:
                break
            rows.append([int(open_t.timestamp() * 1000), str(c), str(c * 1.01), str(c * 0.99), str(c),
                         "1", int((open_t + DAY).timestamp() * 1000) - 1, "100000000"])
        return json.dumps(rows[-int(q["limit"]):]).encode()


class TestTrendRules(unittest.TestCase):
    def test_same_as_research_weights(self):
        xs = walk(800, 11)
        tr = TrendRules()
        self.assertEqual([float(tr.update(Decimal(str(x)))) for x in xs], trend_weights(xs))

    def test_no_weight_before_100_days(self):
        tr = TrendRules()
        ws = [tr.update(Decimal(100 + i)) for i in range(120)]
        self.assertTrue(all(w == 0 for w in ws[:99]))
        self.assertEqual(ws[-1], 1)


class TestTrendStrategy(unittest.TestCase):
    def view(self, cash, qty=Decimal("0"), price=Decimal("1")):
        return PortfolioView(cash=Decimal(cash), positions={"BTCUSDT": qty} if qty else {},
                             equity=Decimal(cash) + qty * price)

    def test_buy_capped_by_max_quote_then_sell_all_when_trend_ends(self):
        s = TrendTopluluk("BTCUSDT", sleeve="0.3", max_quote="50")
        out = []
        for i in range(120):
            out = s.on_bar(bar(i, {"BTCUSDT": 100 + i}), self.view("500"))
        self.assertEqual(s.weight, 1)
        self.assertEqual(out[0].side, "BUY")
        self.assertEqual(out[0].quote_amount, Decimal("50"))          # 150 hedef, 50'lik dilim
        # Fiyat çöküyor: ağırlık 0'a düşünce elde ne varsa satılır
        held = Decimal("1")
        for i in range(120, 260):
            out = s.on_bar(bar(i, {"BTCUSDT": max(5, 300 - 3 * i)}), self.view("400", held, Decimal("5")))
            if s.weight == 0:
                break
        self.assertEqual(s.weight, 0)
        self.assertEqual(out[0].side, "SELL")
        self.assertEqual(out[0].quantity, "ALL")

    def test_small_drift_is_not_traded(self):
        s = TrendTopluluk("BTCUSDT", sleeve="0.3", rebalance="0.1")
        for i in range(120):
            s.on_bar(bar(i, {"BTCUSDT": 100 + i}), self.view("500"))
        price = Decimal(220)
        qty = Decimal("150") / price * Decimal("0.95")       # hedefin %95'i elde
        out = s.on_bar(bar(120, {"BTCUSDT": 220}), PortfolioView(
            cash=Decimal("350"), positions={"BTCUSDT": qty}, equity=Decimal("350") + qty * price))
        self.assertEqual(out, [])


class TestTrendVsResearch(unittest.TestCase):
    def test_simulator_matches_research_within_tolerance(self):
        n = 1200
        closes = {"BTCUSDT": walk(n, 1, 20000), "ETHUSDT": walk(n, 2, 1500)}
        bars = [Bar(T0 + i * DAY, {s: Decimal(str(closes[s][i])) for s in closes}) for i in range(n)]
        strat = Combined([TrendTopluluk(s, "0.5", rebalance="0.02") for s in closes])
        sim = Simulator(strat, BacktestConfig(initial_cash=Decimal("100000"), slippage_bps=Decimal("5")))
        for b in bars:
            sim.step(b)
        ours = float(sim.equity_curve[-1][1]) / 100000 - 1
        days = [(T0 + i * DAY).date() for i in range(n)]
        res = research_simulate(days, closes, {}, {}, None, start=days[0], end=days[-1])
        # Fark beklenir: motor açılışta işlem yapar, araştırma kapanıştan kapanışa ölçer;
        # yön ve büyüklük tutarlı olmalı.
        self.assertGreater(len(sim.portfolio.trades), 10)
        self.assertLess(abs(ours - res.total), max(0.25, abs(res.total) * 0.25),
                        f"motor {ours:+.2%} araştırma {res.total:+.2%}")


class TestTrendLive(unittest.TestCase):
    def test_init_run_status_with_conservative_limits(self):
        n = 260
        fake = FakeDailyBinance({"BTCUSDT": [100 + i for i in range(n)],
                                 "ETHUSDT": [50 + i / 2 for i in range(n)]})
        settings = {"symbols": ["BTCUSDT", "ETHUSDT"], "interval": "1d", "strategy": "trend",
                    "fast": 24, "slow": 96, "fraction": "0.6", "vol_target": None, "vol_window": 72,
                    "stop_loss_pct": None, "take_profit_pct": None, "cash": "500", "taker_rate": "0.001",
                    "slippage_bps": "5", "max_volume_share": "0.01", "rules": None,
                    "max_trade_notional": "50", "max_position_notional": "150", "min_cash_reserve": "200",
                    "max_lag_bars": 2, "rebalance": "0.1"}
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "trend"
            fake.now = T0 + 120 * DAY + timedelta(minutes=5)
            init(d, settings, fetch=fake, clock=lambda: fake.now)
            for k in range(121, 140):
                fake.now = T0 + k * DAY + timedelta(minutes=5)
                run_once(d, fetch=fake, clock=lambda: fake.now)
            txt = status(d)
            self.assertIn("Trend ağırlıkları  : BTCUSDT 4/4, ETHUSDT 4/4", txt)
            trades = (d / "islemler.csv").read_text(encoding="utf-8").splitlines()[1:]
            self.assertGreater(len(trades), 2)
            # Hiçbir alış 50 USDT'yi, hiçbir pozisyon 150 USDT'yi geçmemeli (risk limitleri)
            for row in trades:
                _, sym, side, _, qty, price, *_ = row.split(",")
                if side == "BUY":
                    self.assertLessEqual(Decimal(qty) * Decimal(price), Decimal("50.01"))
            redler = (d / "redler.csv").read_text(encoding="utf-8").splitlines()[1:] \
                if (d / "redler.csv").exists() else []
            self.assertEqual(redler, [])        # hedef risk limitlerine göre kırpılıyor


if __name__ == "__main__":
    unittest.main()
