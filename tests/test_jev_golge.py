"""Jev gölge modu: anahtarsız, ağsız testler (sahte Binance ve sahte Jev)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest import mock

from jev import jev_golge as g
from jev.live import _load, init, run_once, shadow_report, shadow_try
from tests.test_live import ROOT, FakeBinance, settings

HOUR = timedelta(hours=1)


def enable(directory, **kw):
    cfg = {"etkin": True, "ufuk_bar": 3, "her_n_bar": 1, "gunluk_cagri_siniri": 1000}
    cfg.update(kw)
    (Path(directory) / g.CONFIG_FILE).write_text(json.dumps(cfg), encoding="utf-8")


class Runs:
    def __init__(self, symbols=("BTCUSDT",)):
        self.dir = Path(tempfile.mkdtemp()) / "canli"
        self.fake = FakeBinance(("BTCUSDT", "ETHUSDT"))
        self.closes = [t for t, _ in self.fake.candles["BTCUSDT"]]
        self.symbols = list(symbols)

    def at(self, i, minutes=2):
        self.fake.now = self.closes[i] + timedelta(minutes=minutes)
        return lambda: self.fake.now

    def go(self, start, end, predictor=None):
        init(self.dir, settings(symbols=self.symbols), fetch=self.fake, clock=self.at(start))
        for i in range(start + 1, end):
            run_once(self.dir, fetch=self.fake, clock=self.at(i), shadow_predictor=predictor)
        return self


TRADING_FILES = ("islemler.csv", "kararlar.jsonl", "varlik_egrisi.csv", "redler.csv")


class IsolationTests(unittest.TestCase):
    """Gölge mod açık/kapalı, Jev çalışsın ya da çöksün: işlemler birebir aynı olmalı."""

    def test_trades_identical_with_and_without_shadow(self):
        calls = []

        def jev(symbol, history, horizon, step):
            calls.append((symbol, history[-1][0], len(history), horizon))
            return "0.62"

        def boom(*a):
            raise RuntimeError("Jev çöktü")

        def slow(*a):
            time.sleep(5)
            return "0.5"

        base = Runs(("BTCUSDT", "ETHUSDT")).go(40, 160)
        variants = []
        for predictor, cfg in ((jev, {}), (boom, {}), (slow, {"zaman_asimi_sn": 0.05}),
                               (lambda *a: "çok", {})):
            r = Runs(("BTCUSDT", "ETHUSDT"))
            init(r.dir, settings(symbols=r.symbols), fetch=r.fake, clock=r.at(40))
            enable(r.dir, **cfg)
            for i in range(41, 160):
                if predictor is slow and i > 45:
                    predictor = jev            # süreyi kısa tut
                run_once(r.dir, fetch=r.fake, clock=r.at(i), shadow_predictor=predictor)
            variants.append(r)
        a = _load(base.dir).sim
        self.assertGreater(len(a.portfolio.trades), 2)
        for r in variants:
            b = _load(r.dir).sim
            self.assertEqual(a.portfolio.trades, b.portfolio.trades)
            self.assertEqual(a.equity_curve, b.equity_curve)
            for f in TRADING_FILES:
                self.assertEqual((base.dir / f).read_bytes(), (r.dir / f).read_bytes(), f)
        # 1. varyant: 119 bar × 2 sembol; yavaş varyant 46..159 arası jev'e geçer: 114 × 2
        self.assertEqual(len(calls), 2 * 119 + 2 * 114)
        log = (variants[1].dir / "gunluk.log").read_text(encoding="utf-8")
        self.assertIn("tahmini alınamadı (RuntimeError)", log)
        self.assertNotIn("Jev çöktü", log)               # hata metni günlüğe sızmaz
        self.assertIn("tahmini alınamadı (ShadowError)",
                      (variants[2].dir / "gunluk.log").read_text(encoding="utf-8"))
        self.assertFalse((variants[1].dir / g.LOG_FILE).exists())

    def test_disabled_by_default_and_predictor_never_called(self):
        r = Runs().go(40, 50, predictor=lambda *a: self.fail("çağrılmamalı"))
        self.assertFalse((r.dir / g.LOG_FILE).exists())

    def test_missing_key_is_logged_not_raised(self):
        r = Runs()
        init(r.dir, settings(), fetch=r.fake, clock=r.at(40))
        enable(r.dir)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TYPESAFE_API_KEY", None)
            out = run_once(r.dir, fetch=r.fake, clock=r.at(41))
        self.assertEqual(out["islenen"], 1)
        self.assertIn("atlandı (TYPESAFE_API_KEY yok)",
                      (r.dir / "gunluk.log").read_text(encoding="utf-8"))

    def test_bad_config_does_not_stop_trading(self):
        r = Runs()
        init(r.dir, settings(), fetch=r.fake, clock=r.at(40))
        (r.dir / g.CONFIG_FILE).write_text('{"etkin": true, "ufuk_bar": 0}')
        self.assertEqual(run_once(r.dir, fetch=r.fake, clock=r.at(41))["islenen"], 1)
        self.assertIn("ufuk_bar", (r.dir / "gunluk.log").read_text(encoding="utf-8"))


class RecordingTests(unittest.TestCase):
    def test_meaning_of_record_and_resolution(self):
        seen = []

        def jev(symbol, history, horizon, step):
            seen.append((history[-1][0], [t for t, _ in history]))
            return Decimal("0.7")

        r = Runs()
        init(r.dir, settings(), fetch=r.fake, clock=r.at(40))
        enable(r.dir, ufuk_bar=3, gecmis_bar=10)
        for i in range(41, 50):
            run_once(r.dir, fetch=r.fake, clock=r.at(i), shadow_predictor=jev)
        recs = g.read_log(r.dir)
        self.assertEqual(len(recs), 9)
        first = recs[0]
        t0 = r.closes[41]
        self.assertEqual(first["tahmin_zamani"], t0.isoformat())
        self.assertEqual(first["hedef_zaman"], (t0 + 3 * HOUR).isoformat())
        self.assertEqual(first["ufuk_bar"], 3)
        self.assertEqual(first["olasilik"], "0.7")
        close = dict(r.fake.candles["BTCUSDT"])
        self.assertEqual(Decimal(first["fiyat"]), close[t0].close)
        # Tahminci geleceği görmez: geçmişin son elemanı tahmin anı, en fazla 10 kapanış
        for ts, hist in seen:
            self.assertEqual(hist[-1], ts)
            self.assertLessEqual(len(hist), 10)
            self.assertLess(max(hist), ts + HOUR)
        outcomes = g.resolve(recs, _load(r.dir).sim.closes)
        resolved = [o for o in outcomes if o.increased is not None]
        self.assertEqual(len(resolved), 9 - 3)            # son 3 tahmin bekliyor
        for o in resolved:
            t = datetime.fromisoformat(o.record["tahmin_zamani"])
            self.assertEqual(o.increased, close[t + 3 * HOUR].close > close[t].close)
        text = shadow_report(r.dir, r.dir / "sonuc.csv")
        self.assertIn("sonuçlanan: 6", text)
        self.assertIn("bekleyen: 3", text)
        rows = (r.dir / "sonuc.csv").read_text().splitlines()
        self.assertEqual(rows[0].split(","), g.RESULT_HEADER)
        self.assertEqual(len(rows), 10)

    def test_no_duplicate_cadence_daily_limit_and_stale(self):
        n = []
        jev = lambda *a: n.append(a) or "0.5"   # noqa: E731
        r = Runs()
        init(r.dir, settings(), fetch=r.fake, clock=r.at(40))
        enable(r.dir, her_n_bar=4)
        for i in range(41, 61):
            run_once(r.dir, fetch=r.fake, clock=r.at(i), shadow_predictor=jev)
            run_once(r.dir, fetch=r.fake, clock=r.at(i, minutes=20), shadow_predictor=jev)
        times = [datetime.fromisoformat(x["tahmin_zamani"]) for x in g.read_log(r.dir)]
        self.assertEqual(len(times), len(set(times)))      # aynı bar iki kez sorulmaz
        self.assertTrue(all(t.hour % 4 == 0 for t in times))
        self.assertEqual(len(times), 5)

        r2 = Runs()
        init(r2.dir, settings(), fetch=r2.fake, clock=r2.at(40))
        enable(r2.dir, gunluk_cagri_siniri=2)
        for i in range(41, 47):
            run_once(r2.dir, fetch=r2.fake, clock=r2.at(i), shadow_predictor=jev)
        same_day = {}
        for x in g.read_log(r2.dir):
            same_day.setdefault(x["istek_zamani"][:10], 0)
            same_day[x["istek_zamani"][:10]] += 1
        self.assertTrue(all(v <= 2 for v in same_day.values()))
        self.assertIn("günlük çağrı sınırı", (r2.dir / "gunluk.log").read_text(encoding="utf-8"))

        r3 = Runs()
        init(r3.dir, settings(), fetch=r3.fake, clock=r3.at(40))
        enable(r3.dir)
        run_once(r3.dir, fetch=r3.fake, clock=r3.at(50), shadow_predictor=jev)  # 10 saat kesinti
        recs = g.read_log(r3.dir)
        self.assertEqual([x["tahmin_zamani"] for x in recs], [r3.closes[50].isoformat()])

    def test_probability_parsing(self):
        for ok, want in (("0", "0"), (1, "1"), (0.25, "0.25"), (Decimal("0.7"), "0.7")):
            self.assertEqual(g.parse_probability(ok), Decimal(want))
        for bad in (True, None, "abc", "NaN", "-0.01", "1.01", float("inf")):
            with self.assertRaises(g.ShadowError):
                g.parse_probability(bad)

    def test_settings_validation(self):
        d = Path(tempfile.mkdtemp())
        self.assertFalse(g.ShadowSettings.load(d).etkin)
        for body in ('[]', '{"bilinmeyen": 1}', '{"her_n_bar": 0}', '{"zaman_asimi_sn": 500}',
                     '{"ufuk_bar": true}'):
            (d / g.CONFIG_FILE).write_text(body)
            with self.assertRaises(g.ShadowError, msg=body):
                g.ShadowSettings.load(d)


class ReportTests(unittest.TestCase):
    def rec(self, p, up):
        return g.Outcome({"sembol": "X"}, Decimal(p), Decimal(1), up)

    def test_brier_and_baselines(self):
        outs = [self.rec("0.8", True), self.rec("0.8", True), self.rec("0.2", False),
                self.rec("0.6", False), self.rec("0.5", None)]
        text = g.report(outs)
        # (0.04+0.04+0.04+0.36)/4 = 0.12 ; yükseliş oranı %50 → taban 0.25
        self.assertIn("Brier puanı (düşük iyi): 0.1200", text)
        self.assertIn("(50%) bilen: 0.2500", text)
        self.assertIn("3/4 = 75%", text)
        self.assertIn("bekleyen: 1", text)
        self.assertIn("az veri", text)
        self.assertIn("Henüz sonuçlanan tahmin yok", g.report([self.rec("0.5", None)]))


class TypeSafeAdapterTests(unittest.TestCase):
    def fake_sdk(self, value="0.66"):
        calls = {}

        class Noul:
            def __init__(self, instructions):
                self.instructions = instructions

        class Client:
            def __init__(self, model):
                calls["model"] = model

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def system_one(self, state, questions):
                calls["state"], calls["questions"] = state, questions
                return types.SimpleNamespace(
                    nouls={"yukselir": types.SimpleNamespace(noul=value)})

        return types.SimpleNamespace(TypeSafeClient=Client, Noul=Noul), calls

    def test_adapter_sends_only_public_prices_and_exact_question(self):
        sdk, calls = self.fake_sdk()
        t = datetime(2026, 11, 13, 20, tzinfo=timezone.utc)
        hist = [(t - i * HOUR, Decimal(100 + i)) for i in range(5, -1, -1)]
        with mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-olmayan-anahtar"}):
            predict = g.typesafe_predictor("jev-latest", sdk=sdk)
        self.assertEqual(predict("BTCUSDT", hist, 24, HOUR), "0.66")
        q = calls["questions"]["yukselir"].instructions
        self.assertIn("2026-11-14 20:00 UTC", q)            # 24 saat sonrası
        self.assertIn("strictly higher than 100", q)
        self.assertIn("2026-11-13 20:00 UTC", q)
        self.assertIn("BTCUSDT", calls["state"])
        self.assertNotIn("test-olmayan-anahtar", calls["state"] + q)
        self.assertEqual(calls["model"], "jev-latest")

    def test_adapter_requires_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(g.ShadowError):
                g.typesafe_predictor(sdk=self.fake_sdk()[0])


class TryTests(unittest.TestCase):
    def test_try_does_not_write(self):
        r = Runs().go(40, 45)
        text = shadow_try(r.dir, predictor=lambda *a: "0.4")
        self.assertIn("olasılığı 0.4", text)
        self.assertFalse((r.dir / g.LOG_FILE).exists())


class CliTests(unittest.TestCase):
    def test_golge_cli(self):
        r = Runs().go(40, 45)
        out = subprocess.run([sys.executable, "-m", "jev.live", "golge", "--dir", str(r.dir)],
                             cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("Ayar: kapalı", out.stdout)
        self.assertIn("Kayıtlı tahmin: 0", out.stdout)
        shutil.rmtree(r.dir.parent)


if __name__ == "__main__":
    unittest.main()
