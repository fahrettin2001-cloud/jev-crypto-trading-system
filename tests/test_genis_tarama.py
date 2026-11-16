"""Geniş tarama: sahte arşiv ve sentetik fiyatlarla (ağ kullanmaz)."""
import hashlib
import io
import random
import tempfile
import unittest
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from jev import genis_tarama as G
from jev.binance_data import VISION, DownloadError
from jev.duygu import trend_weights

DAY = timedelta(days=1)


def walk(n, seed, drift=0.0005, start=100.0):
    r, p, out = random.Random(seed), start, []
    for _ in range(n):
        p *= 1 + r.gauss(drift, 0.03)
        out.append(p)
    return out


def write_universe(root: Path, folder: str, syms, start: date, n: int, drifts=None, cut=None):
    for k, s in enumerate(syms):
        xs = walk(n, k + 1, (drifts or {}).get(s, 0.0005))
        stop = (cut or {}).get(s, n)
        G._write(root / folder / f"{s}.csv", {start + i * DAY: xs[i] for i in range(stop)})


class FakeArchive:
    def __init__(self, sym, months):
        self.files = {}
        for m in months:
            y, mo = map(int, m.split("-"))
            d0 = date(y, mo, 1)
            rows = []
            d = d0
            while d.month == mo:
                ot = int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)
                rows.append(f"{ot},100,200,99,{100 + d.day},10,{ot + 86_399_999},1000,5,1,100,0\n")
                d += DAY
            name = f"{sym}-1d-{m}"
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr(f"{name}.csv", "".join(rows))
            blob = buf.getvalue()
            url = f"{VISION}/{sym}/1d/{name}.zip"
            self.files[url] = blob
            self.files[url + ".CHECKSUM"] = f"{hashlib.sha256(blob).hexdigest()}  {name}.zip".encode()

    def __call__(self, url):
        if url not in self.files:
            raise DownloadError("HTTP 404")
        return self.files[url]


class TestDownload(unittest.TestCase):
    def test_crypto_download_merges_months_and_skips_missing(self):
        old = G.EVRENLER["kripto"]
        G.EVRENLER["kripto"] = (old[0], ["BTCUSDT"], *old[2:])
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                logs = []
                G.download_crypto(root / "veri", root / "ham", "2020-01", "2020-03",
                                  fetch=FakeArchive("BTCUSDT", ["2020-02", "2020-03"]), log=logs.append)
                s = G._read(root / "veri" / "kripto" / "BTCUSDT.csv")
                self.assertEqual(min(s), date(2020, 2, 1))       # mumun AÇILIŞ günü
                self.assertEqual(max(s), date(2020, 3, 31))
                self.assertEqual(s[date(2020, 2, 3)], 103.0)
                self.assertIn("arşivi olmayan ay: 1", logs[0])
        finally:
            G.EVRENLER["kripto"] = old


class TestUniverse(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_weights_match_single_asset_trend(self):
        write_universe(self.root, "kripto", ["AAAUSDT"], date(2020, 1, 1), 400)
        u = G.Universe({"AAAUSDT": G._read(self.root / "kripto" / "AAAUSDT.csv")})
        xs = [c for c in u.close["AAAUSDT"]]
        self.assertEqual(u.weight["AAAUSDT"], trend_weights(xs))
        self.assertFalse(u.ready["AAAUSDT"][98])
        self.assertTrue(u.ready["AAAUSDT"][99])

    def test_no_look_ahead(self):
        a = walk(500, 1)
        b = a[:300] + [x * 0.2 for x in a[300:]]           # gelecekte çöküş
        d0 = date(2020, 1, 1)
        ua = G.Universe({"X": {d0 + i * DAY: a[i] for i in range(500)}})
        ub = G.Universe({"X": {d0 + i * DAY: b[i] for i in range(500)}})
        ra = ua.simulate(G.Variant(), d0, d0 + 299 * DAY, 0.001, 365)
        rb = ub.simulate(G.Variant(), d0, d0 + 299 * DAY, 0.001, 365)
        self.assertEqual(ra.returns, rb.returns)

    def test_delisted_coin_leaves_universe(self):
        d0 = date(2020, 1, 1)
        up = [100 * 1.01 ** i for i in range(400)]
        u = G.Universe({"A": {d0 + i * DAY: up[i] for i in range(400)},
                        "B": {d0 + i * DAY: up[i] for i in range(250)}})   # 250. günde çıkarıldı
        self.assertTrue(u.ready["B"][249])
        self.assertFalse(u.ready["B"][260])
        t = u.targets(300, G.Variant())
        self.assertNotIn("B", t)
        self.assertAlmostEqual(t["A"], 1.0)                 # tek etkin varlık, tam trend
        self.assertAlmostEqual(u.targets(200, G.Variant())["A"], 0.5)

    def test_variants(self):
        d0 = date(2020, 1, 1)
        prices = {f"S{k}": {d0 + i * DAY: 100 * (1 + 0.001 * (k + 1)) ** i for i in range(300)} for k in range(6)}
        prices["DOWN"] = {d0 + i * DAY: 100 * 0.995 ** i for i in range(300)}
        u = G.Universe(prices)
        eq = u.targets(250, G.Variant())
        self.assertAlmostEqual(sum(eq.values()), 6 / 7)
        self.assertEqual(eq["DOWN"], 0.0)
        top = u.targets(250, G.Variant("enIyiK", k=3))
        self.assertEqual(sorted(top), ["S3", "S4", "S5"])      # en güçlü 3
        self.assertAlmostEqual(sum(top.values()), 1.0)
        self.assertAlmostEqual(sum(u.targets(250, G.Variant("genislik", breadth=0.9)).values()), 0.0)
        self.assertAlmostEqual(sum(u.targets(250, G.Variant("genislik", breadth=0.5)).values()), 6 / 7)

    def test_full_report_runs(self):
        write_universe(self.root, "kripto", G.EVRENLER["kripto"][1][:5], date(2019, 6, 1), 2300)
        write_universe(self.root, "etf", G.EVRENLER["etf"][1][:4], date(2007, 1, 1), 6600)
        rep = G.full_report(self.root)
        for part in ("KRIPTO", "ETF", "HISSE", "Atlandı", "KARIŞIK", "Eğitimde seçilen", "BTC+ETH trend"):
            self.assertIn(part, rep)

    def test_module_has_no_orders(self):
        src = (Path(G.__file__)).read_text(encoding="utf-8")
        for bad in ("portfolio", "run_once", "api_key", "/order"):
            self.assertNotIn(bad, src)


if __name__ == "__main__":
    unittest.main()
