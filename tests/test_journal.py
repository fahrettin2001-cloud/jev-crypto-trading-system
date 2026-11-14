import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from jev.backtest import BacktestConfig, run_backtest
from jev.fees import FeeSchedule
from jev.journal import (Decision, DecisionJournal, calibration, closes_from_bars, evaluate,
                         format_calibration)
from jev.risk import RiskLimits
from jev.strategy import BUY, SELL, Bar, Hold, OrderIntent

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
S = "BTCUSDT"
ROOT = Path(__file__).resolve().parent.parent


def ts(i):
    return T0 + timedelta(hours=i)


def closes(prices, symbol=S):
    return {symbol: [(ts(i), Decimal(str(p))) for i, p in enumerate(prices)]}


def dec(i, action, price, conf=None):
    return Decision(ts(i), S, action, price, conf)


class DecisionTests(unittest.TestCase):
    def test_validation(self):
        with self.assertRaises(ValueError):
            Decision(ts(0), S, "AL", 100)
        with self.assertRaises(ValueError):
            Decision(ts(0), S, BUY, 0)
        with self.assertRaises(ValueError):
            Decision(ts(0), S, BUY, 100, "1.2")
        with self.assertRaises(ValueError):
            Decision(datetime(2026, 1, 1), S, BUY, 100)

    def test_jsonl_roundtrip_lossless(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "k.jsonl"
            j = DecisionJournal(path)
            a = j.record(Decision(ts(0), S, BUY, "63514.45", "0.7312", "jev-1.13.0", "gerekçe"))
            j.record(Decision(ts(1), S, "HOLD", "1", None))
            loaded = DecisionJournal.load(path).decisions
            self.assertEqual(loaded[0], a)
            self.assertEqual(loaded[0].confidence, Decimal("0.7312"))
            self.assertIsNone(loaded[1].confidence)
            path.write_text(path.read_text() + "bozuk\n")
            with self.assertRaisesRegex(ValueError, ":3:"):
                DecisionJournal.load(path)


class EvaluateTests(unittest.TestCase):
    PRICES = [100, 101, 102, 99, 100, 100.1]

    def test_buy_sell_hold_correctness(self):
        out = evaluate([dec(0, BUY, 100), dec(1, SELL, 101), dec(3, "HOLD", 99),
                        dec(4, "HOLD", 100)],
                       closes(self.PRICES), horizon=1, threshold="0.005")
        # 100→101 +%1 > %0,5: AL haklı; 101→102 yükseldi: SAT haksız;
        # 99→100 +%1,01: BEKLE haksız; 100→100.1 +%0,1: BEKLE haklı
        self.assertEqual([o.correct for o in out], [True, False, False, True])
        self.assertEqual(out[0].ret, Decimal("0.01"))

    def test_threshold_requires_beating_costs(self):
        out = evaluate([dec(4, BUY, 100)], closes(self.PRICES), 1, "0.003")
        self.assertFalse(out[0].correct)  # +%0,1 maliyeti karşılamıyor

    def test_unresolved_when_horizon_beyond_data_or_unknown_time(self):
        out = evaluate([dec(5, BUY, 100.1), Decision(ts(0) + timedelta(minutes=30), S, BUY, 100),
                        Decision(ts(0), "ETHUSDT", BUY, 5)],
                       closes(self.PRICES), 1, "0")
        self.assertEqual([o.correct for o in out], [None, None, None])

    def test_validation(self):
        with self.assertRaises(ValueError):
            evaluate([], {}, 0, "0")
        with self.assertRaises(ValueError):
            evaluate([], {}, 1, "-0.1")


class CalibrationTests(unittest.TestCase):
    def outcomes(self):
        # Güven 0.8 olan 10 karar: 8'i haklı. Güven 0.55 olan 10 karar: 3'ü haklı.
        prices = [100] * 41
        ds = []
        for i in range(10):
            prices[2 * i + 1] = 110 if i < 8 else 90
            ds.append(dec(2 * i, BUY, 100, "0.8"))
        for i in range(10, 20):
            prices[2 * i + 1] = 110 if i < 13 else 90
            ds.append(dec(2 * i, BUY, 100, "0.55"))
        ds.append(dec(40, BUY, 100, "1"))   # ölçülemez (veri sonu)
        ds.append(dec(0, SELL, 100))        # güven yok
        return evaluate(ds, closes(prices), 1, "0.003")

    def test_bins_hit_rate_and_gap(self):
        rep = calibration(self.outcomes(), min_count=10)
        rows = {r.low: r for r in rep.rows if r.count}
        self.assertEqual(rows[Decimal("0.8")].count, 10)
        self.assertEqual(rows[Decimal("0.8")].hit_rate, Decimal("0.8"))
        self.assertEqual(rows[Decimal("0.8")].gap, Decimal("0"))
        self.assertEqual(rows[Decimal("0.5")].hit_rate, Decimal("0.3"))
        self.assertEqual(rows[Decimal("0.5")].gap, Decimal("-0.25"))
        self.assertTrue(rows[Decimal("0.5")].enough_data)
        self.assertEqual((rep.evaluated, rep.unresolved, rep.without_confidence), (21, 1, 1))
        self.assertEqual(rep.by_action[BUY], (20, Decimal("0.55")))

    def test_brier(self):
        rep = calibration(self.outcomes())
        # 0.8: 8×0.04 + 2×0.64 = 1.6 ; 0.55: 3×0.2025 + 7×0.3025 = 2.725 ; /20
        self.assertEqual(rep.brier, (Decimal("1.6") + Decimal("2.725")) / 20)

    def test_confidence_one_falls_in_last_bin(self):
        out = evaluate([dec(0, BUY, 100, "1")], closes([100, 110]), 1, "0")
        rep = calibration(out, min_count=1)
        self.assertEqual(rep.rows[-1].count, 1)

    def test_format(self):
        text = format_calibration(calibration(self.outcomes(), min_count=10), 1, "0.003")
        self.assertIn("%50–%60", text)
        self.assertIn("fazla iddialı", text)   # güven %55, isabet %30
        self.assertIn("uyumlu", text)          # güven %80, isabet %80
        self.assertIn("Brier", text)
        few = format_calibration(calibration(self.outcomes(), min_count=15), 1, "0.003")
        self.assertIn("az veri", few)
        self.assertNotIn("fazla iddialı", few)
        no_conf = evaluate([dec(0, BUY, 100)], closes([100, 110]), 1, "0")
        self.assertIn("Güven puanı olan karar yok", format_calibration(calibration(no_conf), 1, 0))

    def test_bad_bins(self):
        with self.assertRaises(ValueError):
            calibration([], bins=[Decimal("0.5"), Decimal("0.5")])


class Scripted:
    name = "senaryo"

    def __init__(self, plan):
        self.plan, self.i = plan, 0

    def on_bar(self, bar, view):
        out = self.plan.get(self.i, [])
        self.i += 1
        return out


class BacktestJournalTests(unittest.TestCase):
    def bars(self, prices):
        return [Bar(ts(i), {S: p}) for i, p in enumerate(prices)]

    def test_all_decisions_logged_with_status(self):
        s = Scripted({0: [OrderIntent(S, BUY, quantity=1, confidence="0.7", reason="a")],
                      1: [Hold(S, reason="bekle", confidence="0.6"),
                          OrderIntent(S, BUY, quantity=100, confidence="0.9")],   # pahalı: risk
                      3: [OrderIntent(S, SELL, quantity="ALL", confidence="0.5")]})  # veri biter
        with tempfile.TemporaryDirectory() as d:
            j = DecisionJournal(Path(d) / "k.jsonl")
            r = run_backtest(self.bars([100, 100, 100, 100]), s,
                             BacktestConfig(initial_cash=1000, fees=FeeSchedule("0", "0"),
                                            risk=RiskLimits(max_trade_notional="500")), journal=j)
            self.assertEqual(len(DecisionJournal.load(j.path).decisions), 4)
        self.assertEqual([d.action for d in r.decisions], [BUY, "HOLD", BUY, SELL])
        status = [d.status for d in r.decisions]
        self.assertEqual(status[0], "gerçekleşti")
        self.assertEqual(status[1], "bekle")
        self.assertTrue(status[2].startswith("reddedildi:"))
        self.assertIn("Veri bitti", status[3])
        self.assertEqual(r.decisions[0].confidence, Decimal("0.7"))
        self.assertEqual(r.decisions[0].source, "senaryo")
        self.assertEqual(r.decisions[0].price, Decimal("100"))

    def test_hold_does_not_trade(self):
        r = run_backtest(self.bars([100, 100]), Scripted({0: [Hold(S)]}),
                         BacktestConfig(initial_cash=1000))
        self.assertEqual(r.trades, [])
        self.assertEqual(r.rejections, [])

    def test_hold_validation(self):
        with self.assertRaises(ValueError):
            Hold("", confidence="0.5")
        with self.assertRaises(ValueError):
            Hold(S, confidence="2")

    def test_closes_from_bars(self):
        c = closes_from_bars(self.bars([1, 2]))
        self.assertEqual(c[S][1], (ts(1), Decimal("2")))


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True,
                              timeout=120)

    def test_backtest_calibration_and_journal_cli(self):
        with tempfile.TemporaryDirectory() as d:
            j = Path(d) / "k.jsonl"
            out = self.run_cli("-m", "jev.backtest", "--prices",
                               "data/synthetic_klines/BTCUSDT-1h-sentetik.csv",
                               "--kline-symbols", "BTCUSDT", "--fast", "24", "--slow", "96",
                               "--calibration", "--journal", str(j), "--out", d)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("Karar isabeti", out.stdout)
            self.assertTrue((Path(d) / "kararlar.csv").exists())
            again = self.run_cli("-m", "jev.journal", "--journal", str(j), "--prices",
                                 "data/synthetic_klines/BTCUSDT-1h-sentetik.csv",
                                 "--kline-symbols", "BTCUSDT")
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertIn("Genel isabet", again.stdout)
            bad = self.run_cli("-m", "jev.journal", "--journal", str(Path(d) / "yok.jsonl"),
                               "--prices", "data/sample_prices.csv")
            self.assertEqual(bad.returncode, 1)
            self.assertNotIn("Traceback", bad.stderr)


if __name__ == "__main__":
    unittest.main()
