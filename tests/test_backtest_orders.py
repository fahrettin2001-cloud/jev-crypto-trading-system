import csv
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from jev.backtest import (K_LIMIT, K_MARKET, K_STOP, K_TAKE, BacktestConfig, run_backtest,
                          write_results)
from jev.exchange_rules import ExchangeRules, SymbolRules
from jev.fees import FeeSchedule
from jev.risk import RiskLimits
from jev.strategy import BUY, LIMIT, SELL, Bar, OrderIntent, SmaCross

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
S = "BTCUSDT"
NO_FEES = FeeSchedule(maker_rate="0", taker_rate="0")


def ohlc(rows, volume=None):
    """rows: (open, high, low, close) listesi."""
    out = []
    for i, (o, h, l, c) in enumerate(rows):
        out.append(Bar(T0 + timedelta(hours=i), {S: c}, {S: o}, {S: h}, {S: l},
                       {S: volume} if volume is not None else None))
    return out


class Scripted:
    name = "senaryo"

    def __init__(self, plan):
        self.plan, self.i = plan, 0

    def on_bar(self, bar, view):
        out = self.plan.get(self.i, [])
        self.i += 1
        return out


def cfg(**kw):
    kw.setdefault("initial_cash", 10000)
    kw.setdefault("fees", NO_FEES)
    return BacktestConfig(**kw)


class BarTests(unittest.TestCase):
    def test_defaults_and_inconsistent_ohlc(self):
        b = Bar(T0, {S: 100})
        self.assertEqual((b.open(S), b.high(S), b.low(S)), (100, 100, 100))
        self.assertIsNone(b.quote_volume(S))
        with self.assertRaises(ValueError):
            Bar(T0, {S: 100}, {S: 90}, {S: 95}, {S: 85})  # kapanış > yüksek
        with self.assertRaises(ValueError):
            Bar(T0, {S: 100}, opens={"ETHUSDT": 5})


class MarketAtOpenTests(unittest.TestCase):
    def test_market_order_fills_at_next_open(self):
        s = Scripted({0: [OrderIntent(S, BUY, quantity=1)]})
        r = run_backtest(ohlc([(100, 101, 99, 100), (105, 110, 104, 108)]), s, cfg())
        self.assertEqual(r.trades[0].price, Decimal("105"))
        self.assertEqual(r.notes[0].kind, K_MARKET)


class ProtectiveExitTests(unittest.TestCase):
    def buy_with(self, rows, **exits):
        s = Scripted({0: [OrderIntent(S, BUY, quantity=1, **exits)]})
        return run_backtest(ohlc(rows), s, cfg(slippage_bps=100))

    def test_stop_loss_intrabar(self):
        r = self.buy_with([(100, 100, 100, 100), (100, 101, 99, 100), (99, 99, 90, 92)],
                          stop_loss=95)
        sell = r.trades[1]
        self.assertEqual(r.notes[1].kind, K_STOP)
        self.assertEqual(sell.price, Decimal("95") * Decimal("0.99"))  # kayma uygulanır
        self.assertNotIn(S, r.portfolio.positions)

    def test_stop_loss_gap_fills_at_open(self):
        r = self.buy_with([(100, 100, 100, 100), (100, 101, 99, 100), (80, 85, 78, 82)],
                          stop_loss=95)
        self.assertEqual(r.trades[1].price, Decimal("80") * Decimal("0.99"))
        self.assertIn("boşluğu", r.notes[1].reason)

    def test_take_profit_fills_at_level_without_slippage_maker_fee(self):
        s = Scripted({0: [OrderIntent(S, BUY, quantity=1, take_profit=110)]})
        rows = [(100, 100, 100, 100), (100, 101, 99, 100), (101, 115, 100, 112)]
        r = run_backtest(ohlc(rows), s, cfg(fees=FeeSchedule(maker_rate="0.0002",
                                                             taker_rate="0.001")))
        sell = r.trades[1]
        self.assertEqual(r.notes[1].kind, K_TAKE)
        self.assertEqual(sell.price, Decimal("110"))
        self.assertEqual(sell.fee, Decimal("110") * Decimal("0.0002"))

    def test_both_touched_same_bar_assumes_stop_first(self):
        r = self.buy_with([(100, 100, 100, 100), (100, 101, 99, 100), (100, 120, 80, 100)],
                          stop_loss=90, take_profit=110)
        self.assertEqual(r.notes[1].kind, K_STOP)

    def test_exit_levels_rounded_to_tick_with_rules(self):
        rules = ExchangeRules({S: SymbolRules(S, "BTC", "USDT", min_price="0.01",
                                              tick_size="0.01")})
        s = Scripted({0: [OrderIntent(S, BUY, quantity=1, take_profit="110.004")]})
        rows = [(100,) * 4, (100,) * 4, (105, 112, 104, 111)]
        r = run_backtest(ohlc(rows), s, cfg(rules=rules))
        self.assertEqual(r.trades[1].price, Decimal("110.01"))

    def test_exit_not_checked_on_entry_bar(self):
        # Alış barı 2'nin açılışında; aynı barın düşüğü stop'un altında olsa da
        # alıştan önce mi sonra mı olduğu bilinmez → o barda tetiklenmez.
        r = self.buy_with([(100, 100, 100, 100), (100, 101, 80, 100), (100, 101, 99, 100)],
                          stop_loss=95)
        self.assertEqual(len(r.trades), 1)
        self.assertIn(S, r.portfolio.positions)

    def test_exits_cleared_after_strategy_sells(self):
        s = Scripted({0: [OrderIntent(S, BUY, quantity=1, stop_loss=95)],
                      1: [OrderIntent(S, SELL, quantity="ALL")],
                      2: [OrderIntent(S, BUY, quantity=1)]})
        rows = [(100,) * 4, (100,) * 4, (100,) * 4, (100,) * 4, (90, 90, 50, 60)]
        r = run_backtest(ohlc(rows), s, cfg())
        # Son alışta stop yok; eski stop yeni pozisyonu satmamalı
        self.assertEqual([t.side for t in r.trades], [BUY, SELL, BUY])

    def test_exit_bypasses_risk_limit(self):
        risk = RiskLimits(max_trade_notional="600")
        s = Scripted({0: [OrderIntent(S, BUY, quantity=5, stop_loss=150)]})
        rows = [(100,) * 4, (100,) * 4, (200,) * 4, (200, 200, 140, 145)]
        r = run_backtest(ohlc(rows), s, cfg(risk=risk))
        # Alış 5 * 100 = 500 <= 600 geçer; çıkış 5 * 150 = 750 > 600 olsa da
        # zarar durdur risk limitine takılmamalı (pozisyon kilitli kalmasın).
        self.assertEqual([n.kind for n in r.notes], [K_MARKET, K_STOP])
        self.assertEqual(r.trades[1].quantity * r.trades[1].price, Decimal("750"))
        self.assertNotIn(S, r.portfolio.positions)

    def test_stop_and_take_validation(self):
        with self.assertRaises(ValueError):
            OrderIntent(S, BUY, quantity=1, stop_loss=110, take_profit=100)
        with self.assertRaises(ValueError):
            OrderIntent(S, SELL, quantity=1, stop_loss=90)

    def test_sma_with_stop_loss_runs(self):
        closes = [100 - i for i in range(10)] + [90 + 3 * i for i in range(8)] + [60] * 3
        rows = [(c, c, c, c) for c in closes]
        r = run_backtest(ohlc(rows), SmaCross(S, 2, 4, stop_loss_pct="0.05"), cfg())
        self.assertIn(K_STOP, [n.kind for n in r.notes])


class LimitOrderTests(unittest.TestCase):
    def test_buy_limit_fills_when_low_touches(self):
        s = Scripted({0: [OrderIntent(S, BUY, quantity=1, order_type=LIMIT, limit_price=95,
                                      good_for_bars=3)]})
        rows = [(100,) * 4, (100, 101, 97, 100), (99, 100, 94, 96), (96,) * 4]
        r = run_backtest(ohlc(rows), s,
                         cfg(fees=FeeSchedule(maker_rate="0.0002", taker_rate="0.001"),
                             slippage_bps=50))
        t = r.trades[0]
        self.assertEqual((t.price, t.timestamp), (Decimal("95"), T0 + timedelta(hours=2)))
        self.assertEqual(t.fee, Decimal("95") * Decimal("0.0002"))
        self.assertEqual(r.notes[0].kind, K_LIMIT)

    def test_buy_limit_gap_fills_at_better_open(self):
        s = Scripted({0: [OrderIntent(S, BUY, quantity=1, order_type=LIMIT, limit_price=95)]})
        r = run_backtest(ohlc([(100,) * 4, (90, 92, 88, 91)]), s, cfg())
        self.assertEqual(r.trades[0].price, Decimal("90"))

    def test_sell_limit(self):
        s = Scripted({0: [OrderIntent(S, BUY, quantity=1)],
                      1: [OrderIntent(S, SELL, quantity="ALL", order_type=LIMIT,
                                      limit_price=110, good_for_bars=2)]})
        rows = [(100,) * 4, (100,) * 4, (105, 109, 104, 108), (108, 112, 107, 111)]
        r = run_backtest(ohlc(rows), s, cfg())
        self.assertEqual(r.trades[1].price, Decimal("110"))

    def test_limit_expires(self):
        s = Scripted({0: [OrderIntent(S, BUY, quantity=1, order_type=LIMIT, limit_price=50,
                                      good_for_bars=2)]})
        r = run_backtest(ohlc([(100,) * 4] * 5), s, cfg())
        self.assertEqual(r.trades, [])
        self.assertEqual(len(r.rejections), 1)
        self.assertIn("süresi doldu", r.rejections[0].reason)
        self.assertEqual(r.rejections[0].timestamp, T0 + timedelta(hours=2))

    def test_limit_open_at_data_end_recorded(self):
        s = Scripted({0: [OrderIntent(S, BUY, quantity=1, order_type=LIMIT, limit_price=50,
                                      good_for_bars=10)]})
        r = run_backtest(ohlc([(100,) * 4] * 3), s, cfg())
        self.assertIn("açık kaldı", r.rejections[0].reason)

    def test_limit_price_filter_checked_at_placement(self):
        rules = ExchangeRules({S: SymbolRules(S, "BTC", "USDT", min_price="0.01",
                                              tick_size="0.01")})
        s = Scripted({0: [OrderIntent(S, BUY, quantity=1, order_type=LIMIT,
                                      limit_price="95.005")]})
        r = run_backtest(ohlc([(100,) * 4, (90,) * 4]), s, cfg(rules=rules))
        self.assertEqual(r.trades, [])
        self.assertIn("PRICE_FILTER", r.rejections[0].reason)

    def test_limit_with_stop_sets_exit(self):
        s = Scripted({0: [OrderIntent(S, BUY, quantity=1, order_type=LIMIT, limit_price=95,
                                      stop_loss=90)]})
        rows = [(100,) * 4, (96, 97, 94, 95), (95, 95, 85, 86)]
        r = run_backtest(ohlc(rows), s, cfg())
        self.assertEqual([n.kind for n in r.notes], [K_LIMIT, K_STOP])

    def test_strategy_sees_open_limit_orders(self):
        seen = []

        class Watch:
            name = "izle"

            def __init__(self):
                self.i = 0

            def on_bar(self, bar, view):
                seen.append(len(view.open_orders))
                self.i += 1
                if self.i == 1:
                    return [OrderIntent(S, BUY, quantity=1, order_type=LIMIT, limit_price=50,
                                        good_for_bars=2)]
                return []

        run_backtest(ohlc([(100,) * 4] * 5), Watch(), cfg())
        # bar0'da verildi; bar1 ve bar2'de denenir. bar1 kapanışında hâlâ açık,
        # bar2'de denendikten sonra süresi dolar (strateji bar2'yi görmeden önce).
        self.assertEqual(seen, [0, 1, 0, 0, 0])

    def test_limit_validation(self):
        with self.assertRaises(ValueError):
            OrderIntent(S, BUY, quantity=1, order_type=LIMIT)
        with self.assertRaises(ValueError):
            OrderIntent(S, BUY, quantity=1, limit_price=5)
        with self.assertRaises(ValueError):
            OrderIntent(S, BUY, quantity=1, order_type=LIMIT, limit_price=5, good_for_bars=0)


class LiquidityTests(unittest.TestCase):
    def test_order_above_volume_share_rejected(self):
        s = Scripted({0: [OrderIntent(S, BUY, quantity=2)],   # 200 > %1 * 10000 = 100
                      1: [OrderIntent(S, BUY, quantity="0.5")]})  # 50 <= 100
        r = run_backtest(ohlc([(100,) * 4] * 3, volume=10000), s,
                         cfg(max_volume_share="0.01"))
        self.assertEqual(len(r.trades), 1)
        self.assertEqual(r.trades[0].quantity, Decimal("0.5"))
        self.assertIn("Likidite", r.rejections[0].reason)

    def test_unknown_volume_not_limited(self):
        s = Scripted({0: [OrderIntent(S, BUY, quantity=2)]})
        r = run_backtest(ohlc([(100,) * 4] * 2), s, cfg(max_volume_share="0.01"))
        self.assertEqual(len(r.trades), 1)

    def test_config_validation(self):
        for v in ("0", "1.5", "-0.1"):
            with self.assertRaises(ValueError):
                cfg(max_volume_share=v)


class ExportTests(unittest.TestCase):
    def test_write_results(self):
        s = Scripted({0: [OrderIntent(S, BUY, quantity=1, reason="deneme", stop_loss=95)],
                      2: [OrderIntent(S, BUY, quantity=1000)]})
        rows = [(100,) * 4, (100,) * 4, (99, 99, 90, 92), (92,) * 4]
        r = run_backtest(ohlc(rows), s, cfg())
        with tempfile.TemporaryDirectory() as d:
            paths = write_results(r, d)
            self.assertEqual(sorted(p.name for p in paths),
                             ["islemler.csv", "ozet.json", "redler.csv", "varlik_egrisi.csv"])
            trades = list(csv.DictReader(open(Path(d) / "islemler.csv", encoding="utf-8")))
            self.assertEqual([t["tur"] for t in trades], [K_MARKET, K_STOP])
            self.assertEqual(trades[0]["gerekce"], "deneme")
            equity = list(csv.DictReader(open(Path(d) / "varlik_egrisi.csv", encoding="utf-8")))
            self.assertEqual(len(equity), 4)
            summary = json.loads((Path(d) / "ozet.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["metrikler"]["trades"], 2)
            self.assertEqual(summary["reddedilen"], 1)
            Decimal(summary["metrikler"]["total_return"])  # kayıpsız metin


if __name__ == "__main__":
    unittest.main()


class RiskOnSellTests(unittest.TestCase):
    def test_trade_limit_does_not_block_selling_a_grown_position(self):
        # 40 USDT'lik alış limite (50) uyar; fiyat iki katına çıkınca satış 80 USDT
        # olur. Satış riski azalttığı için tutar sınırına takılmamalı.
        risk = RiskLimits(max_trade_notional="50", allowed_symbols=[S])
        s = Scripted({0: [OrderIntent(S, BUY, quantity="0.4")],
                      2: [OrderIntent(S, SELL, quantity="ALL")]})
        rows = [(100,) * 4, (100,) * 4, (200,) * 4, (200,) * 4]
        r = run_backtest(ohlc(rows), s, cfg(risk=risk))
        self.assertEqual([t.side for t in r.trades], [BUY, SELL])
        self.assertEqual(r.trades[1].quantity * r.trades[1].price, Decimal("80"))
        self.assertEqual(r.rejections, [])

    def test_trade_limit_still_blocks_large_buys(self):
        risk = RiskLimits(max_trade_notional="50")
        s = Scripted({0: [OrderIntent(S, BUY, quantity=1)]})
        r = run_backtest(ohlc([(100,) * 4] * 2), s, cfg(risk=risk))
        self.assertEqual(r.trades, [])
        self.assertIn("risk", r.rejections[0].reason)


class MaxQuoteTests(unittest.TestCase):
    def test_sma_buy_capped_by_max_quote(self):
        from jev.strategy import PortfolioView
        closes = [100 - i for i in range(8)] + [92 + 3 * i for i in range(8)]
        strat = SmaCross(S, 2, 4, fraction="0.95", max_quote="50")
        for i, c in enumerate(closes):
            out = strat.on_bar(Bar(T0 + timedelta(hours=i), {S: c}),
                               PortfolioView(Decimal("1000"), equity=Decimal("1000")))
            if out:
                self.assertEqual(out[0].quote_amount, Decimal("50"))
                return
        self.fail("alış önerisi gelmedi")

    def test_invalid_max_quote(self):
        with self.assertRaises(ValueError):
            SmaCross(S, 2, 4, max_quote="0")
