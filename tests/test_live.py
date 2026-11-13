"""Canlı sanal işlem: sahte Binance cevaplarıyla (ağ kullanmaz)."""
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from jev.backtest import Simulator, run_backtest
from jev.klines import bars_from_series, load_binance_klines
from jev.live import (LiveError, STOP, build_config, build_strategy, check,
                      fetch_closed_candles, init, run_once, status, warmup_bars_needed)

ROOT = Path(__file__).resolve().parent.parent
SYNTH = {s: ROOT / "data" / "synthetic_klines" / f"{s}-1h-sentetik.csv"
         for s in ("BTCUSDT", "ETHUSDT")}
HOUR = timedelta(hours=1)


class FakeBinance:
    """data-api.binance.vision/api/v3/klines taklidi: `now` anına kadar açılmış mumları verir
    (son mum henüz kapanmamış olabilir; gerçek API gibi)."""

    def __init__(self, symbols=("BTCUSDT",)):
        self.candles = {s: sorted(load_binance_klines(SYNTH[s]).items()) for s in symbols}
        self.now = None
        self.calls = 0

    def __call__(self, url):
        self.calls += 1
        q = dict(p.split("=") for p in url.split("?")[1].split("&"))
        rows = []
        for close_time, c in self.candles[q["symbol"]]:
            open_time = close_time - HOUR
            if open_time >= self.now:
                break
            rows.append([int(open_time.timestamp() * 1000), str(c.open), str(c.high), str(c.low),
                         str(c.close), "1", int(close_time.timestamp() * 1000) - 1,
                         str(c.quote_volume), 1, "0", "0", "0"])
        return json.dumps(rows[-int(q["limit"]):]).encode()


def settings(**kw):
    s = {"symbols": ["BTCUSDT"], "interval": "1h", "strategy": "sma", "fast": 6, "slow": 24,
         "fraction": "0.95", "vol_target": "0.01", "vol_window": 24, "stop_loss_pct": "0.03",
         "take_profit_pct": None, "cash": "10000", "taker_rate": "0.001", "slippage_bps": "5",
         "max_volume_share": "0.01", "rules": str(ROOT / "data" / "exchange_info_sample.json"),
         "max_trade_notional": "5000", "max_position_notional": None, "min_cash_reserve": "1000",
         "max_lag_bars": 2}
    s.update(kw)
    return s


class FetchTests(unittest.TestCase):
    def test_only_closed_candles(self):
        fake = FakeBinance()
        first_close = fake.candles["BTCUSDT"][0][0]
        fake.now = first_close + 5 * HOUR + timedelta(minutes=30)
        # Kapananlar: first_close .. first_close+5s (6 mum); first_close+6s'de kapanacak
        # mum açık ve sahte API onu da döndürüyor (gerçek API gibi) → alınmamalı
        self.assertEqual(len(json.loads(fake("x?symbol=BTCUSDT&interval=1h&limit=10"))), 7)
        got = fetch_closed_candles("BTCUSDT", "1h", 10, fake.now, fake)
        self.assertEqual(len(got), 6)
        self.assertEqual(max(got), first_close + 5 * HOUR)

    def test_bad_responses(self):
        now = datetime(2026, 2, 1, tzinfo=timezone.utc)
        for body in (b"nope", b"{}", b'[[1,"a"]]',
                     json.dumps([[0, "1", "0.5", "1", "1", "1", 3599999, "1"]]).encode(),   # h<o
                     json.dumps([[0, "1", "1", "1", "1", "1", 59999, "1"]]).encode()):     # 1 dk
            with self.assertRaises(LiveError):
                fetch_closed_candles("BTCUSDT", "1h", 5, now, lambda u, b=body: b)
        with self.assertRaises(ValueError):
            fetch_closed_candles("btc/usdt", "1h", 5, now, lambda u: b"[]")

    def test_check(self):
        fake = FakeBinance()
        fake.now = fake.candles["BTCUSDT"][10][0] + timedelta(minutes=5)
        self.assertIn("Bağlantı tamam", check(fake, lambda: fake.now))


class LiveRunTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp()) / "canli"
        self.fake = FakeBinance(("BTCUSDT", "ETHUSDT"))
        self.closes = [t for t, _ in self.fake.candles["BTCUSDT"]]

    def at(self, i, minutes=2):
        """i'nci mumun kapanışından birkaç dakika sonrası."""
        self.fake.now = self.closes[i] + timedelta(minutes=minutes)
        return lambda: self.fake.now

    def test_hourly_runs_match_backtest_exactly(self):
        st = settings()
        start, end = 40, 400
        init(self.dir, st, fetch=self.fake, clock=self.at(start))
        load = __import__("jev.live", fromlist=["_load"])._load
        warm = {ts for ts, _ in load(self.dir).sim.equity_curve}     # ısınmada gösterilen barlar
        self.assertGreaterEqual(len(warm), warmup_bars_needed(st))
        for i in range(start + 1, end):
            run_once(self.dir, fetch=self.fake, clock=self.at(i))   # her saat kaydet-yükle
        live = load(self.dir).sim

        # Aynı barlar tek seferde: ısınma barları gözlem, sonrakiler işlem
        series = {"BTCUSDT": dict(self.fake.candles["BTCUSDT"])}
        sim = Simulator(build_strategy(st), build_config(st))
        for b in bars_from_series(series):
            if b.timestamp in warm:
                sim.observe(b)
            elif min(warm) < b.timestamp <= self.closes[end - 1]:
                sim.step(b)
        self.assertGreater(len(live.portfolio.trades), 2)
        self.assertEqual(live.portfolio.trades, sim.portfolio.trades)
        self.assertEqual(live.equity_curve, sim.equity_curve)
        self.assertEqual(live.portfolio.cash, sim.portfolio.cash)

        trades_csv = (self.dir / "islemler.csv").read_text().strip().splitlines()
        self.assertEqual(len(trades_csv) - 1, len(sim.portfolio.trades))
        equity_csv = (self.dir / "varlik_egrisi.csv").read_text().strip().splitlines()
        self.assertEqual(len(equity_csv) - 1, end - start - 1)
        decisions = [json.loads(l) for l in (self.dir / "kararlar.jsonl").read_text().splitlines()]
        self.assertTrue(decisions)
        self.assertTrue(all(d["status"] != "bekliyor" for d in decisions))
        self.assertIn("Toplam getiri", status(self.dir))

    def test_catches_up_after_downtime_and_skips_stale(self):
        init(self.dir, settings(), fetch=self.fake, clock=self.at(40))
        out = run_once(self.dir, fetch=self.fake, clock=self.at(50))   # 10 saat kesinti
        self.assertEqual(out["islenen"] + out["eski_atlanan"], 10)
        self.assertEqual(out["islenen"], 2)                             # son 2 bar güncel
        self.assertEqual(out["eski_atlanan"], 8)
        again = run_once(self.dir, fetch=self.fake, clock=self.at(50, minutes=20))
        self.assertEqual(again["islenen"], 0)                           # aynı bar iki kez işlenmez

    def test_stop_file(self):
        init(self.dir, settings(), fetch=self.fake, clock=self.at(40))
        (self.dir / STOP).touch()
        calls = self.fake.calls
        out = run_once(self.dir, fetch=self.fake, clock=self.at(41))
        self.assertTrue(out["durduruldu"])
        self.assertEqual(self.fake.calls, calls)                        # ağa bile çıkmaz
        self.assertIn("AÇIK", status(self.dir))

    def test_multi_symbol(self):
        init(self.dir, settings(symbols=["BTCUSDT", "ETHUSDT"]), fetch=self.fake,
             clock=self.at(40))
        for i in range(41, 200):
            run_once(self.dir, fetch=self.fake, clock=self.at(i))
        sim = __import__("jev.live", fromlist=["_load"])._load(self.dir).sim
        self.assertEqual({t.symbol for t in sim.portfolio.trades}, {"BTCUSDT", "ETHUSDT"})
        self.assertTrue(all(t.quantity * t.price <= 5000 for t in sim.portfolio.trades
                            if t.side == "BUY"))

    def test_errors(self):
        with self.assertRaises(LiveError):
            run_once(self.dir, fetch=self.fake, clock=self.at(40))      # init yok
        init(self.dir, settings(), fetch=self.fake, clock=self.at(40))
        with self.assertRaises(LiveError):
            init(self.dir, settings(), fetch=self.fake, clock=self.at(40))  # iki kez
        with self.assertRaises(ValueError):
            init(Path(tempfile.mkdtemp()), settings(symbols=["btc"]), fetch=self.fake,
                 clock=self.at(40))

    def test_failed_fetch_leaves_state_untouched(self):
        init(self.dir, settings(), fetch=self.fake, clock=self.at(40))
        before = (self.dir / "durum.pkl").read_bytes()

        def broken(url):
            raise LiveError("bağlantı yok")
        with self.assertRaises(LiveError):
            run_once(self.dir, fetch=broken, clock=self.at(41))
        self.assertEqual((self.dir / "durum.pkl").read_bytes(), before)
        out = run_once(self.dir, fetch=self.fake, clock=self.at(41))
        self.assertEqual(out["islenen"], 1)

    def test_cli_help_and_error(self):
        out = subprocess.run([sys.executable, "-m", "jev.live", "status", "--dir",
                              str(Path(tempfile.mkdtemp()) / "yok")], cwd=ROOT,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 1)
        self.assertIn("init", out.stderr)
        self.assertNotIn("Traceback", out.stderr)


if __name__ == "__main__":
    unittest.main()
