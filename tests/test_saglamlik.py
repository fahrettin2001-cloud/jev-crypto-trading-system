"""Sağlamlık testi aracı: sentetik veriyle (ağsız)."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from jev import saglamlik as sg
from jev.klines import load_bars

ROOT = Path(__file__).resolve().parent.parent
SYNTH = ROOT / "data" / "synthetic_klines"
UTC = timezone.utc


def run(label, periods):
    r = sg.Run(label, {}, [], Decimal(0), 0, Decimal(0), Decimal(1))
    r.period_returns = {k: Decimal(v) for k, v in periods.items()}
    return r


class HelperTests(unittest.TestCase):
    def test_period_returns_compound_to_total(self):
        t = datetime(2026, 3, 31, 22, tzinfo=UTC)
        eq = [(t, Decimal(100)), (t + timedelta(hours=1), Decimal(110)),
              (t + timedelta(hours=2), Decimal(121)), (t + timedelta(days=95), Decimal(99))]
        pr = sg.period_returns(eq, Decimal(100))
        self.assertEqual(list(pr), ["2026-Ç1", "2026-Ç2", "2026-Ç3"])
        self.assertEqual(pr["2026-Ç1"], Decimal("0.1"))
        self.assertEqual(pr["2026-Ç2"], Decimal("0.1"))          # 110 → 121
        self.assertEqual(sg._compound(pr.values()), Decimal("-0.01"))

    def test_walk_forward_uses_only_previous_period(self):
        a = run("A", {"Q1": "0.2", "Q2": "-0.1", "Q3": "0.05"})
        b = run("B", {"Q1": "0.1", "Q2": "0.3", "Q3": "-0.2"})
        wf = sg.walk_forward([a, b], ["Q1", "Q2", "Q3"])
        self.assertEqual(wf, [("Q2", "A", Decimal("-0.1")), ("Q3", "B", Decimal("-0.2"))])

    def test_buy_and_hold_equal_weight(self):
        from jev.strategy import Bar
        t = datetime(2026, 1, 1, tzinfo=UTC)
        bars = [Bar(t, {"X": Decimal(10), "Y": Decimal(100)}),
                Bar(t + timedelta(hours=1), {"X": Decimal(20), "Y": Decimal(50)})]
        self.assertEqual(sg.buy_and_hold(bars, ["X", "Y"])[-1][1], Decimal("1.25"))


class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths = [SYNTH / "BTCUSDT-1h-sentetik.csv", SYNTH / "ETHUSDT-1h-sentetik.csv"]
        cls.bars = load_bars(paths, kline_symbols=["BTCUSDT", "ETHUSDT"])
        cls.a = sg.analyse(cls.bars, ["BTCUSDT", "ETHUSDT"],
                           str(ROOT / "data" / "exchange_info_sample.json"),
                           fasts=(12, 24), slows=(48, 96))

    def test_live_run_matches_live_settings_and_limits(self):
        live = self.a["live"]
        self.assertEqual(live.initial, Decimal("500"))
        self.assertEqual(live.settings["max_trade_notional"], "50")
        self.assertLessEqual(live.exposure, Decimal("0.6"))   # en az 200 USDT nakit kalır

    def test_grid_and_period_consistency(self):
        grid = self.a["grid"]
        self.assertEqual({r.label for r in grid}, {"12/48", "12/96", "24/48", "24/96"})
        for r in grid:
            self.assertAlmostEqual(float(sg._compound(r.period_returns.values())),
                                   float(r.total_return), places=9)
            self.assertTrue(Decimal(0) <= r.exposure <= Decimal(1))

    def test_report_and_cli(self):
        text = sg.report(self.a)
        for part in ("## 1. Özet", "## 2. Ayar ızgarası", "**", "## 3. Çeyrek çeyrek",
                     "İleriye dönük seçim", "## 4. Maliyet"):
            self.assertIn(part, text)
        d = Path(tempfile.mkdtemp())
        for s in ("BTCUSDT", "ETHUSDT"):
            (d / f"{s}-1h-2026-01.csv").write_bytes((SYNTH / f"{s}-1h-sentetik.csv").read_bytes())
        out = d / "rapor"
        sg.main(["--veri", str(d), "--out", str(out)])
        self.assertIn("Strateji sağlamlık testi", (out / "saglamlik.md").read_text("utf-8"))
        self.assertTrue((out / "saglamlik.json").exists())


if __name__ == "__main__":
    unittest.main()
