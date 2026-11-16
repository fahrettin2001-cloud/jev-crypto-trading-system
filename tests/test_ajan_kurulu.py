"""Ajan kurulu (TradingAgents gölge modu): sahte ajan ve sahte Binance ile, ağ ve
TradingAgents kurulumu olmadan."""
import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from jev.ajan_kurulu import (AjanError, HORIZON_DAYS, rating_to_action, run_day,
                             summary_text, tradingagents_runner)
from jev.journal import BUY, HOLD, SELL, DecisionJournal

DAY = timedelta(days=1)
START = datetime(2026, 10, 1, tzinfo=timezone.utc)


class FakeDailyBinance:
    """Günlük mumlar: fiyat her gün sabit oranda artar. `now` öncesi açılanları verir."""

    def __init__(self, days=40, step=Decimal("0.02")):
        self.closes = {}
        p = Decimal("100")
        for i in range(days):
            p = p * (1 + step)
            self.closes[START + i * DAY] = p   # açılış zamanı → kapanış fiyatı
        self.now = None
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        q = dict(x.split("=") for x in url.split("?")[1].split("&"))
        assert q["interval"] == "1d"
        rows = []
        for open_t, c in self.closes.items():
            if open_t >= self.now:
                break
            close_ms = int((open_t + DAY).timestamp() * 1000) - 1
            rows.append([int(open_t.timestamp() * 1000), str(c), str(c * 2), str(c / 2), str(c),
                         "1", close_ms, "1000"])
        return json.dumps(rows[-int(q["limit"]):]).encode()


class FakeRunner:
    model = "sahte:derin/hizli"

    def __init__(self, signals):
        self.signals = signals
        self.calls = []

    def __call__(self, symbol, trade_date):
        self.calls.append((symbol, trade_date))
        sig = self.signals[symbol]
        if isinstance(sig, Exception):
            raise sig
        return {"market_report": f"{symbol} trend yukarı", "final_trade_decision": f"Rating: {sig}"}, sig


class TestAjanKurulu(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "ajan"
        self.fetch = FakeDailyBinance()

    def tearDown(self):
        self.tmp.cleanup()

    def clock_at(self, t):
        self.fetch.now = t
        return lambda: t

    def test_rating_mapping(self):
        self.assertEqual(rating_to_action("Buy"), (BUY, ""))
        self.assertEqual(rating_to_action("Overweight")[0], BUY)
        self.assertEqual(rating_to_action("hold")[0], HOLD)
        self.assertEqual(rating_to_action("Underweight")[0], SELL)
        self.assertEqual(rating_to_action(" Sell ")[0], SELL)
        action, status = rating_to_action("REVIEW")
        self.assertEqual(action, HOLD)
        self.assertTrue(status.startswith("inceleme"))

    def test_run_records_decisions_reports_and_summary(self):
        day = date(2026, 10, 10)
        clock = self.clock_at(datetime(2026, 10, 11, 0, 40, tzinfo=timezone.utc))
        runner = FakeRunner({"BTCUSDT": "Overweight", "ETHUSDT": "Sell"})
        msgs = run_day(self.dir, ["BTCUSDT", "ETHUSDT"], day, runner, fetch=self.fetch, clock=clock)
        self.assertEqual(runner.calls, [("BTCUSDT", "2026-10-10"), ("ETHUSDT", "2026-10-10")])
        self.assertEqual(len(msgs), 2)
        decisions = DecisionJournal.load(self.dir / "ajan_kararlar.jsonl").decisions
        self.assertEqual([(d.symbol, d.action) for d in decisions], [("BTCUSDT", BUY), ("ETHUSDT", SELL)])
        d = decisions[0]
        # Kayıt zamanı analiz gününün kapanışı; fiyat o günün kapanışı (geleceği görme yok).
        self.assertEqual(d.timestamp, datetime(2026, 10, 11, tzinfo=timezone.utc))
        self.assertEqual(d.price, self.fetch.closes[datetime(2026, 10, 10, tzinfo=timezone.utc)])
        self.assertTrue(d.source.startswith("tradingagents:sahte"))
        report = (self.dir / "raporlar" / "2026-10-10-BTCUSDT.md").read_text(encoding="utf-8")
        self.assertIn("Overweight", report)
        self.assertIn("trend yukarı", report)
        self.assertIn("emir yok", report)
        self.assertTrue((self.dir / "ozet.md").exists())

    def test_same_day_not_rerun(self):
        day = date(2026, 10, 10)
        clock = self.clock_at(datetime(2026, 10, 11, 1, tzinfo=timezone.utc))
        runner = FakeRunner({"BTCUSDT": "Buy"})
        run_day(self.dir, ["BTCUSDT"], day, runner, fetch=self.fetch, clock=clock)
        msgs = run_day(self.dir, ["BTCUSDT"], day, runner, fetch=self.fetch, clock=clock)
        self.assertEqual(len(runner.calls), 1)
        self.assertIn("atlandı", msgs[0])

    def test_one_symbol_error_does_not_stop_others(self):
        clock = self.clock_at(datetime(2026, 10, 11, 1, tzinfo=timezone.utc))
        runner = FakeRunner({"BTCUSDT": RuntimeError("LLM zaman aşımı"), "ETHUSDT": "Hold"})
        msgs = run_day(self.dir, ["BTCUSDT", "ETHUSDT"], date(2026, 10, 10), runner,
                       fetch=self.fetch, clock=clock)
        self.assertIn("HATA", msgs[0])
        decisions = DecisionJournal.load(self.dir / "ajan_kararlar.jsonl").decisions
        self.assertEqual([d.symbol for d in decisions], ["ETHUSDT"])
        self.assertIn("HATA", (self.dir / "gunluk.log").read_text(encoding="utf-8"))

    def test_review_signal_recorded_as_hold_for_inspection(self):
        clock = self.clock_at(datetime(2026, 10, 11, 1, tzinfo=timezone.utc))
        run_day(self.dir, ["BTCUSDT"], date(2026, 10, 10), FakeRunner({"BTCUSDT": "REVIEW"}),
                fetch=self.fetch, clock=clock)
        d = DecisionJournal.load(self.dir / "ajan_kararlar.jsonl").decisions[0]
        self.assertEqual(d.action, HOLD)
        self.assertTrue(d.status.startswith("inceleme"))

    def test_refuses_unclosed_day(self):
        clock = self.clock_at(datetime(2026, 10, 10, 12, tzinfo=timezone.utc))
        runner = FakeRunner({"BTCUSDT": "Buy"})
        with self.assertRaises(AjanError):
            run_day(self.dir, ["BTCUSDT"], date(2026, 10, 10), runner, fetch=self.fetch, clock=clock)
        self.assertEqual(runner.calls, [])

    def test_invalid_symbol_rejected(self):
        clock = self.clock_at(datetime(2026, 10, 11, 1, tzinfo=timezone.utc))
        with self.assertRaises(ValueError):
            run_day(self.dir, ["btc/../x"], date(2026, 10, 10), FakeRunner({}), fetch=self.fetch, clock=clock)

    def test_summary_measures_hits_after_horizon(self):
        # Fiyat sürekli artıyor: BUY haklı, SELL haksız çıkmalı.
        clock = self.clock_at(datetime(2026, 10, 11, 1, tzinfo=timezone.utc))
        run_day(self.dir, ["BTCUSDT", "ETHUSDT"], date(2026, 10, 10),
                FakeRunner({"BTCUSDT": "Buy", "ETHUSDT": "Sell"}), fetch=self.fetch, clock=clock)
        later = self.clock_at(datetime(2026, 10, 11 + HORIZON_DAYS, 1, tzinfo=timezone.utc))
        text = summary_text(self.dir, fetch=self.fetch, clock=later)
        self.assertIn("| BUY | 1 | %100 (1/1) |", text)
        self.assertIn("| SELL | 1 | %0 (0/1) |", text)
        self.assertIn("evet", text)
        self.assertIn("hayır", text)

    def test_summary_without_decisions(self):
        self.assertIn("Henüz karar yok", summary_text(self.dir))

    def test_module_never_touches_portfolio_or_orders(self):
        src = (Path(__file__).resolve().parent.parent / "jev" / "ajan_kurulu.py").read_text(encoding="utf-8")
        for forbidden in ("portfolio", "storage", "SQLitePortfolio", "run_once", "api_key", "order"):
            self.assertNotIn(forbidden, src, forbidden)

    def test_missing_tradingagents_gives_clear_error(self):
        saved = {k: sys.modules.get(k) for k in ("tradingagents", "tradingagents.default_config")}
        sys.modules["tradingagents"] = None   # içe aktarmayı engelle
        try:
            with self.assertRaises(AjanError) as ctx:
                tradingagents_runner()
            self.assertIn("kurulu değil", str(ctx.exception))
        finally:
            for k, v in saved.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v


if __name__ == "__main__":
    unittest.main()
