import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from jev.backtest import BacktestConfig, format_report, run_backtest
from jev.exchange_rules import ExchangeRules, SymbolRules
from jev.fees import FeeSchedule
from jev.klines import bars_from_series, load_bars, load_binance_kline_csv
from jev.metrics import max_drawdown
from jev.risk import RiskLimits
from jev.strategy import BUY, SELL, Bar, BuyAndHold, OrderIntent

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parent.parent


def bars(prices, symbol="BTCUSDT"):
    return [Bar(T0 + timedelta(hours=i), {symbol: p}) for i, p in enumerate(prices)]


class Scripted:
    """Belirli bar sıralarında verilen önerileri döndüren test stratejisi."""
    name = "senaryo"

    def __init__(self, plan):
        self.plan, self.i, self.views = plan, 0, []

    def on_bar(self, bar, view):
        self.views.append(view)
        out = self.plan.get(self.i, [])
        self.i += 1
        return out


NO_FEES = FeeSchedule(maker_rate="0", taker_rate="0")


class ExecutionTests(unittest.TestCase):
    def test_next_bar_execution_uses_following_price(self):
        s = Scripted({0: [OrderIntent("BTCUSDT", BUY, quantity=1)]})
        r = run_backtest(bars([100, 120, 130]), s, BacktestConfig(initial_cash=1000, fees=NO_FEES))
        self.assertEqual(r.trades[0].price, Decimal("120"))
        self.assertEqual(r.trades[0].timestamp, T0 + timedelta(hours=1))

    def test_same_bar_execution_uses_current_price(self):
        s = Scripted({0: [OrderIntent("BTCUSDT", BUY, quantity=1)]})
        r = run_backtest(bars([100, 120]), s,
                         BacktestConfig(initial_cash=1000, fees=NO_FEES, execution="same_bar"))
        self.assertEqual(r.trades[0].price, Decimal("100"))

    def test_strategy_sees_trade_in_next_view(self):
        s = Scripted({0: [OrderIntent("BTCUSDT", BUY, quantity=2)]})
        run_backtest(bars([100, 100, 100]), s, BacktestConfig(initial_cash=1000, fees=NO_FEES))
        self.assertEqual(s.views[0].quantity("BTCUSDT"), 0)
        self.assertEqual(s.views[1].quantity("BTCUSDT"), 2)
        self.assertEqual(s.views[1].cash, Decimal("800"))

    def test_fees_and_slippage_exact(self):
        # Alış 100 → kayma 1% → 101; 2 adet = 202, komisyon %0,1 = 0.202
        # Satış 110 → 108.9; 2 adet = 217.8, komisyon 0.2178
        s = Scripted({0: [OrderIntent("BTCUSDT", BUY, quantity=2)],
                      1: [OrderIntent("BTCUSDT", SELL, quantity="ALL")]})
        cfg = BacktestConfig(initial_cash=1000, fees=FeeSchedule(taker_rate="0.001"),
                             slippage_bps=100)
        r = run_backtest(bars([90, 100, 110]), s, cfg)
        buy, sell = r.trades
        self.assertEqual(buy.price, Decimal("101"))
        self.assertEqual(sell.price, Decimal("108.9"))
        expected_cash = Decimal("1000") - Decimal("202.202") + Decimal("217.8") - Decimal("0.2178")
        self.assertEqual(r.portfolio.cash, expected_cash)
        self.assertEqual(r.metrics.final_equity, expected_cash)
        self.assertEqual(r.metrics.total_fees, Decimal("0.4198"))

    def test_quote_amount_buy_fits_budget_including_fee(self):
        s = Scripted({0: [OrderIntent("BTCUSDT", BUY, quote_amount=1000)]})
        r = run_backtest(bars([1, 3, 3]), s,
                         BacktestConfig(initial_cash=1000, fees=FeeSchedule(taker_rate="0.001")))
        self.assertEqual(len(r.trades), 1)
        self.assertGreaterEqual(r.portfolio.cash, 0)
        self.assertLess(r.portfolio.cash, Decimal("0.01"))

    def test_quote_amount_larger_than_cash_is_capped(self):
        s = Scripted({0: [OrderIntent("BTCUSDT", BUY, quote_amount=5000)]})
        r = run_backtest(bars([10, 10, 10]), s, BacktestConfig(initial_cash=1000, fees=NO_FEES))
        self.assertEqual(r.trades[0].quantity, Decimal("100"))

    def test_rules_floor_quantity_and_reject_min_notional(self):
        rules = ExchangeRules({"BTCUSDT": SymbolRules(
            "BTCUSDT", "BTC", "USDT", min_qty="0.001", max_qty="100", step_size="0.001",
            min_notional="5")})
        s = Scripted({0: [OrderIntent("BTCUSDT", BUY, quantity="1.23456")],
                      1: [OrderIntent("BTCUSDT", BUY, quantity="0.002")]})  # 0.002*100 = 0.2 < 5
        r = run_backtest(bars([100, 100, 100]), s,
                         BacktestConfig(initial_cash=1000, fees=NO_FEES, rules=rules))
        self.assertEqual(r.trades[0].quantity, Decimal("1.234"))
        self.assertEqual(len(r.rejections), 1)
        self.assertIn("NOTIONAL", r.rejections[0].reason)

    def test_unknown_symbol_in_rules_rejected(self):
        rules = ExchangeRules({"ETHUSDT": SymbolRules("ETHUSDT", "ETH", "USDT")})
        s = Scripted({0: [OrderIntent("BTCUSDT", BUY, quantity=1)]})
        r = run_backtest(bars([10, 10]), s,
                         BacktestConfig(initial_cash=1000, fees=NO_FEES, rules=rules))
        self.assertEqual(r.trades, [])
        self.assertIn("kural", r.rejections[0].reason)

    def test_risk_limits_reject_without_changing_portfolio(self):
        risk = RiskLimits(max_trade_notional="50")
        s = Scripted({0: [OrderIntent("BTCUSDT", BUY, quantity=1)]})
        r = run_backtest(bars([100, 100]), s,
                         BacktestConfig(initial_cash=1000, fees=NO_FEES, risk=risk))
        self.assertEqual(r.trades, [])
        self.assertEqual(r.portfolio.cash, Decimal("1000"))
        self.assertIn("risk", r.rejections[0].reason)

    def test_after_buy_risk_check_rolls_back(self):
        risk = RiskLimits(min_cash_reserve="950")
        s = Scripted({0: [OrderIntent("BTCUSDT", BUY, quantity=1)]})
        r = run_backtest(bars([100, 100]), s,
                         BacktestConfig(initial_cash=1000, fees=NO_FEES, risk=risk))
        self.assertEqual(r.trades, [])
        self.assertEqual(r.portfolio.positions, {})
        self.assertEqual(r.portfolio.cash, Decimal("1000"))

    def test_insufficient_cash_and_sell_without_position_rejected(self):
        s = Scripted({0: [OrderIntent("BTCUSDT", BUY, quantity=100),
                          OrderIntent("BTCUSDT", SELL, quantity="ALL")]})
        r = run_backtest(bars([100, 100]), s, BacktestConfig(initial_cash=1000, fees=NO_FEES))
        self.assertEqual(r.trades, [])
        self.assertEqual(len(r.rejections), 2)

    def test_pending_intent_at_end_recorded(self):
        s = Scripted({1: [OrderIntent("BTCUSDT", BUY, quantity=1)]})
        r = run_backtest(bars([100, 100]), s, BacktestConfig(initial_cash=1000, fees=NO_FEES))
        self.assertEqual(r.trades, [])
        self.assertIn("Veri bitti", r.rejections[0].reason)

    def test_missing_price_carries_forward_for_valuation(self):
        series = bars_from_series({
            "BTCUSDT": {T0: Decimal("100"), T0 + timedelta(hours=1): Decimal("100"),
                        T0 + timedelta(hours=3): Decimal("100")},
            "ETHUSDT": {T0 + timedelta(hours=2): Decimal("50")},
        })
        s = Scripted({0: [OrderIntent("BTCUSDT", BUY, quantity=1)]})
        r = run_backtest(series, s, BacktestConfig(initial_cash=1000, fees=NO_FEES))
        self.assertEqual([v for _, v in r.equity_curve], [Decimal("1000")] * 4)

    def test_intent_for_symbol_missing_in_bar_rejected(self):
        series = bars_from_series({
            "BTCUSDT": {T0: Decimal("100")},
            "ETHUSDT": {T0 + timedelta(hours=1): Decimal("50")},
        })
        s = Scripted({0: [OrderIntent("BTCUSDT", BUY, quantity=1)]})
        r = run_backtest(series, s, BacktestConfig(initial_cash=1000, fees=NO_FEES))
        self.assertIn("fiyat yok", r.rejections[0].reason)

    def test_unsorted_bars_and_bad_strategy_output_rejected(self):
        with self.assertRaises(ValueError):
            run_backtest(list(reversed(bars([1, 2]))), Scripted({}))
        with self.assertRaises(ValueError):
            run_backtest([], Scripted({}))
        with self.assertRaises(TypeError):
            run_backtest(bars([1, 2]), Scripted({0: ["BUY BTC"]}))

    def test_config_validation(self):
        for kwargs in ({"initial_cash": 0}, {"slippage_bps": -1}, {"execution": "x"}):
            with self.assertRaises(ValueError):
                BacktestConfig(**kwargs)


class MetricsTests(unittest.TestCase):
    def test_max_drawdown(self):
        vals = [Decimal(v) for v in (100, 120, 90, 130, 65, 140)]
        self.assertEqual(max_drawdown(vals), Decimal("0.5"))  # 130 → 65
        self.assertEqual(max_drawdown([Decimal(1), Decimal(2)]), 0)

    def test_round_trip_metrics(self):
        s = Scripted({0: [OrderIntent("BTCUSDT", BUY, quantity=1)],
                      1: [OrderIntent("BTCUSDT", SELL, quantity="ALL")],
                      2: [OrderIntent("BTCUSDT", BUY, quantity=1)],
                      3: [OrderIntent("BTCUSDT", SELL, quantity="ALL")]})
        r = run_backtest(bars([100, 100, 150, 150, 120]), s,
                         BacktestConfig(initial_cash=1000, fees=NO_FEES))
        m = r.metrics
        # 100'den al, 150'den sat (+50); 150'den al, 120'den sat (-30)
        self.assertEqual((m.buys, m.sells), (2, 2))
        self.assertEqual(m.win_rate, Decimal("0.5"))
        self.assertEqual(m.realized_pnl, Decimal("20"))
        self.assertEqual(m.total_return, Decimal("0.02"))
        self.assertEqual(m.bars, 5)

    def test_buy_and_hold_benchmark(self):
        r = run_backtest(bars([100, 100, 200]), BuyAndHold("BTCUSDT"),
                         BacktestConfig(initial_cash=1000, fees=NO_FEES))
        self.assertEqual(r.metrics.total_return, Decimal("1"))
        self.assertIn("al-tut", format_report(r, r))


class KlineLoaderTests(unittest.TestCase):
    def write(self, text):
        d = tempfile.mkdtemp()
        p = Path(d) / "k.csv"
        p.write_text(text)
        return p

    def test_millisecond_and_microsecond_timestamps(self):
        # 2026-01-01 00:00 UTC = 1767225600000 ms
        ms = self.write("1767225600000,100,101,99,100.5,10,1767229199999,1005,0,0,0,0\n")
        us = self.write("1767225600000000,100,101,99,100.5,10,1767229199999999,1005,0,0,0,0\n")
        expected = {datetime(2026, 1, 1, 1, tzinfo=timezone.utc): Decimal("100.5")}
        self.assertEqual(load_binance_kline_csv(ms, "BTCUSDT"), expected)
        self.assertEqual(load_binance_kline_csv(us, "BTCUSDT"), expected)

    def test_header_skipped_and_bad_rows_rejected(self):
        p = self.write("open_time,open,high,low,close,volume,close_time\n"
                       "1767225600000,99,101,98,100,10,1767229199999,0,0,0,0,0\n")
        self.assertEqual(len(load_binance_kline_csv(p, "X")), 1)
        with self.assertRaises(ValueError):
            load_binance_kline_csv(self.write("1767225600000,1,2\n"), "X")
        with self.assertRaises(ValueError):
            load_binance_kline_csv(self.write("1767225600000,1,2,0.5,0,10,1767229199999\n"), "X")

    def test_load_bars_multi_file(self):
        a = self.write("1767225600000,99,101,98,100,10,1767229199999,1000,0,0,0,0\n")
        b = self.write("1767225600000,49,51,48,50,10,1767229199999,500,0,0,0,0\n")
        result = load_bars([a, b], kline_symbols=["BTCUSDT", "ETHUSDT"])
        self.assertEqual(dict(result[0].prices), {"BTCUSDT": Decimal("100"), "ETHUSDT": Decimal("50")})
        with self.assertRaises(ValueError):
            load_bars([a, b], kline_symbols=["BTCUSDT"])


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "jev.backtest", *args], cwd=ROOT,
                              capture_output=True, text=True, timeout=60)

    def test_cli_runs_on_sample_data(self):
        out = self.run_cli("--fast", "2", "--slow", "3", "--rules", "data/exchange_info_sample.json")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("Toplam getiri", out.stdout)
        self.assertIn("Kıyas", out.stdout)

    def test_cli_error_is_clean(self):
        out = self.run_cli("--prices", "yok.csv")
        self.assertEqual(out.returncode, 1)
        self.assertIn("Hata", out.stderr)
        self.assertNotIn("Traceback", out.stderr)


if __name__ == "__main__":
    unittest.main()
