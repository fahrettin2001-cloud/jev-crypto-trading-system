"""Duygu endeksi: sahte alternative.me ve Binance cevaplarıyla (ağ kullanmaz)."""
import json
import random
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from jev.duygu import (Filter, apply_filter, backtest_report, daily, download, fetch_daily_closes,
                       fetch_funding_daily, fng_label, funding_annual_7d, load, simulate,
                       trend_weights)

DAY = timedelta(days=1)


def ms(d):
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


class FakeWeb:
    """alternative.me + Binance spot günlük mum + vadeli fonlama + long/short taklidi."""

    def __init__(self, start=date(2017, 9, 1), end=date(2025, 6, 30), seed=7):
        rnd = random.Random(seed)
        self.days = [start + i * DAY for i in range((end - start).days + 1)]
        self.prices = {}
        for s, p in (("BTCUSDT", 4000.0), ("ETHUSDT", 300.0)):
            series = {}
            for d in self.days:
                p *= 1 + rnd.gauss(0.0008, 0.035)
                series[d] = p
            self.prices[s] = series
        self.fng = {d: rnd.randint(5, 95) for d in self.days if d >= date(2018, 2, 1)}
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        u = urlparse(url)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if "alternative.me" in u.netloc:
            rows = [{"value": str(v), "value_classification": "x",
                     "timestamp": str(ms(d) // 1000)} for d, v in sorted(self.fng.items(), reverse=True)]
            return json.dumps({"data": rows}).encode()
        if u.path.endswith("/klines"):
            st = int(q["startTime"])
            rows = [[ms(d), "1", "1", "1", f"{p:.4f}", "1", ms(d + DAY) - 1, "1"]
                    for d, p in self.prices[q["symbol"]].items() if ms(d) >= st][: int(q["limit"])]
            return json.dumps(rows).encode()
        if u.path.endswith("/fundingRate"):
            st = int(q["startTime"])
            rows = []
            for d in self.days:
                if d < date(2019, 9, 10):
                    continue
                for h in (0, 8, 16):
                    t = ms(d) + h * 3600_000
                    if t >= st:
                        rows.append({"symbol": q["symbol"], "fundingTime": t, "fundingRate": "0.0001"})
            return json.dumps(rows[: int(q["limit"])]).encode()
        if "LongShort" in u.path:
            rows = [{"symbol": q["symbol"], "longShortRatio": "1.5", "timestamp": ms(d)} for d in self.days[-30:]]
            return json.dumps(rows).encode()
        raise AssertionError(url)


class TestDuygu(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.web = FakeWeb()

    def tearDown(self):
        self.tmp.cleanup()

    def test_closes_paginate_and_stop_at_end(self):
        got = fetch_daily_closes("BTCUSDT", date(2017, 9, 1), date(2021, 1, 5), self.web)
        self.assertEqual(min(got), date(2017, 9, 1))
        self.assertEqual(max(got), date(2021, 1, 5))
        self.assertEqual(len(got), (date(2021, 1, 5) - date(2017, 9, 1)).days + 1)
        self.assertGreater(sum("klines" in c for c in self.web.calls), 1)   # sayfalandı

    def test_funding_daily_sum_and_pagination(self):
        got = fetch_funding_daily("BTCUSDT", date(2019, 9, 10), date(2020, 12, 31), self.web)
        self.assertAlmostEqual(got[date(2020, 1, 1)], 0.0003)
        self.assertEqual(max(got), date(2020, 12, 31))
        self.assertGreater(sum("fundingRate" in c for c in self.web.calls), 1)
        self.assertAlmostEqual(funding_annual_7d(got, date(2020, 6, 1)), 0.0003 * 365)

    def test_download_excludes_today(self):
        today = date(2025, 6, 30)
        msgs = download(self.dir, self.web, today=today)
        self.assertTrue(any("Korku" in m for m in msgs))
        days, closes, fng, funding = load(self.dir)
        self.assertEqual(days[-1], today - DAY)
        self.assertNotIn(today, fng)
        self.assertTrue(funding["BTCUSDT"])

    def test_trend_weights_do_not_look_ahead(self):
        closes = [100 + i for i in range(300)]
        w1 = trend_weights(closes)
        changed = closes[:200] + [1.0] * 100
        w2 = trend_weights(changed)
        self.assertEqual(w1[:200], w2[:200])
        self.assertEqual(w1[150], 1.0)          # sürekli yükselişte tam yatırım
        self.assertEqual(w1[50], 0.0)           # 100 gün dolmadan yatırım yok

    def test_filter_rules(self):
        self.assertEqual(apply_filter(1.0, Filter(greed=80), 85, None), 0.5)
        self.assertEqual(apply_filter(1.0, Filter(greed=80), 79, None), 1.0)
        self.assertEqual(apply_filter(0.0, Filter(fear=20), 15, None), 0.5)
        self.assertEqual(apply_filter(0.0, Filter(fear=20), None, None), 0.0)  # veri yoksa dokunma
        self.assertEqual(apply_filter(1.0, Filter(funding=0.3), None, 0.4), 0.5)
        self.assertEqual(apply_filter(1.0, Filter(), 90, 0.9), 1.0)
        self.assertEqual(fng_label(10), "aşırı korku")
        self.assertEqual(fng_label(80), "aşırı açgözlülük")

    def test_greed_filter_reduces_exposure(self):
        download(self.dir, self.web, today=date(2025, 6, 30))
        days, closes, fng, funding = load(self.dir)
        base = simulate(days, closes, fng, funding, None, start=date(2018, 2, 1), end=days[-1])
        half = simulate(days, closes, fng, funding, Filter(greed=50), start=date(2018, 2, 1), end=days[-1])
        bh = simulate(days, closes, fng, funding, None, start=date(2018, 2, 1), end=days[-1], buy_hold=True)
        self.assertLess(half.exposure, base.exposure)
        self.assertAlmostEqual(bh.exposure, 1.0)
        self.assertGreater(base.cost, 0)

    def test_backtest_report(self):
        download(self.dir, self.web, today=date(2025, 6, 30))
        rep = backtest_report(self.dir)
        for part in ("Eğitimde seçilen filtre", "Test dönemi", "Al-tut", "Trend topluluğu", "Izgara",
                     "alternative.me"):
            self.assertIn(part, rep)

    def test_daily_record_once(self):
        today = date(2025, 6, 30)
        rec = daily(self.dir, self.web, today=today)
        self.assertEqual(rec["gun"], "2025-06-29")
        self.assertIn("korku_acgozluluk", rec)
        self.assertAlmostEqual(rec["fonlama_yillik_7g_BTCUSDT"], round(0.0003 * 365, 4))
        self.assertEqual(rec["long_short_BTCUSDT"], 1.5)
        daily(self.dir, self.web, today=today)
        lines = (self.dir / "duygu_kayit.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn("2025-06-29", (self.dir / "duygu_ozet.md").read_text(encoding="utf-8"))

    def test_module_has_no_orders_or_portfolio(self):
        src = (Path(__file__).resolve().parent.parent / "jev" / "duygu.py").read_text(encoding="utf-8")
        for forbidden in ("portfolio", "storage", "run_once", "api_key", "/order"):
            self.assertNotIn(forbidden, src)


if __name__ == "__main__":
    unittest.main()
