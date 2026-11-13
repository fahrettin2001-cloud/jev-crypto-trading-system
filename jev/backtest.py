"""Geriye dönük test (backtest) motoru — yalnızca sanal, ağ bağlantısı yok.

Her bar için:
1. Önceki barda verilen öneriler bu barın fiyatıyla (varsayılan) gerçekleştirilir.
   Strateji barın kapanışını gördükten sonra karar verdiği için aynı fiyattan
   işlem yapması geleceği görmek olurdu; `execution="same_bar"` yalnızca
   karşılaştırma içindir.
2. Fiyata kayma (slippage) eklenir: alış daha pahalı, satış daha ucuz.
3. Miktar Binance işlem kurallarına göre aşağı yuvarlanır ve doğrulanır.
4. Risk kontrolü (`RiskLimits`) uygulanır; alış sonrası kontroller deneme
   kopyası üzerinde yapılır, geçmezse portföy değişmez.
5. Portföy son bilinen fiyatlarla değerlenir, varlık eğrisine eklenir.
6. Stratejiye salt okunur görünüm verilir, yeni öneriler alınır.

Reddedilen her öneri nedeniyle birlikte kaydedilir.
"""

from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from typing import Sequence

from .exchange_rules import ExchangeRules
from .fees import D, FeeSchedule
from .metrics import Metrics, compute_metrics
from .portfolio import Portfolio, Trade, TradeError
from .risk import RiskLimits
from .strategy import BUY, Bar, BuyAndHold, OrderIntent, PortfolioView, SmaCross, Strategy

BPS = Decimal("10000")
# Kural dosyası yoksa Binance'in 8 ondalık hassasiyeti varsayılır.
DEFAULT_QTY_STEP = Decimal("0.00000001")


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: Decimal = Decimal("10000")
    fees: FeeSchedule = field(default_factory=FeeSchedule)
    slippage_bps: Decimal = Decimal("0")
    rules: ExchangeRules | None = None
    risk: RiskLimits | None = None
    execution: str = "next_bar"  # ya da "same_bar"
    quote: str = "USDT"

    def __post_init__(self) -> None:
        cash, slip = D(self.initial_cash), D(self.slippage_bps)
        if not cash.is_finite() or cash <= 0:
            raise ValueError("Başlangıç nakdi pozitif olmalı")
        if not slip.is_finite() or not 0 <= slip < BPS:
            raise ValueError("Kayma 0 ile 10000 bps arasında olmalı")
        if self.execution not in ("next_bar", "same_bar"):
            raise ValueError("execution 'next_bar' ya da 'same_bar' olmalı")
        object.__setattr__(self, "initial_cash", cash)
        object.__setattr__(self, "slippage_bps", slip)


@dataclass(frozen=True)
class Rejection:
    timestamp: datetime
    intent: OrderIntent
    reason: str


@dataclass
class BacktestResult:
    strategy: str
    config: BacktestConfig
    portfolio: Portfolio
    equity_curve: list[tuple[datetime, Decimal]]
    rejections: list[Rejection]
    metrics: Metrics

    @property
    def trades(self) -> list[Trade]:
        return self.portfolio.trades


def run_backtest(bars: Sequence[Bar], strategy: Strategy, config: BacktestConfig | None = None
                 ) -> BacktestResult:
    config = config or BacktestConfig()
    if not bars:
        raise ValueError("Backtest için en az bir bar gerekli")
    if any(b.timestamp >= c.timestamp for b, c in zip(bars, bars[1:])):
        raise ValueError("Barlar zaman sırasına göre ve tekrarsız olmalı")

    portfolio = Portfolio(cash=config.initial_cash, fees=config.fees, quote=config.quote)
    last_prices: dict[str, Decimal] = {}
    equity_curve: list[tuple[datetime, Decimal]] = []
    rejections: list[Rejection] = []
    pending: list[OrderIntent] = []

    for bar in bars:
        last_prices.update(bar.prices)
        if config.execution == "next_bar":
            for intent in pending:
                portfolio = _execute(portfolio, intent, bar, config, rejections)
            pending = []

        view = PortfolioView(
            cash=portfolio.cash,
            positions={s: p.quantity for s, p in portfolio.positions.items()},
            equity=portfolio.equity(last_prices),
        )
        intents = list(strategy.on_bar(bar, view) or [])
        for intent in intents:
            if not isinstance(intent, OrderIntent):
                raise TypeError(f"Strateji OrderIntent dışında değer döndürdü: {intent!r}")
        if config.execution == "same_bar":
            for intent in intents:
                portfolio = _execute(portfolio, intent, bar, config, rejections)
        else:
            pending = intents

        equity_curve.append((bar.timestamp, portfolio.equity(last_prices)))

    for intent in pending:
        rejections.append(Rejection(bars[-1].timestamp, intent,
                                    "Veri bitti; öneri gerçekleştirilemedi"))

    return BacktestResult(
        strategy=getattr(strategy, "name", type(strategy).__name__),
        config=config,
        portfolio=portfolio,
        equity_curve=equity_curve,
        rejections=rejections,
        metrics=compute_metrics(equity_curve, portfolio.trades, config.initial_cash),
    )


def _execute(portfolio: Portfolio, intent: OrderIntent, bar: Bar, config: BacktestConfig,
             rejections: list[Rejection]) -> Portfolio:
    """Öneriyi dener; başarılıysa yeni portföyü, değilse eskisini döndürür."""
    def reject(reason: str) -> Portfolio:
        rejections.append(Rejection(bar.timestamp, intent, reason))
        return portfolio

    price = bar.prices.get(intent.symbol)
    if price is None:
        return reject(f"{intent.symbol} için bu barda fiyat yok")
    slip = config.slippage_bps / BPS
    fill = price * (1 + slip) if intent.side == BUY else price * (1 - slip)
    rules = None
    if config.rules is not None:
        try:
            rules = config.rules[intent.symbol]
        except TradeError as exc:
            return reject(str(exc))

    # Miktarı belirle
    if intent.side == BUY:
        if intent.quote_amount is not None:
            budget = min(intent.quote_amount, portfolio.cash)
            # Komisyon dahil bütçeye sığan miktar
            quantity = budget / (fill * (1 + config.fees.taker_rate))
        else:
            quantity = intent.quantity
    else:
        held = portfolio.positions[intent.symbol].quantity if intent.symbol in portfolio.positions \
            else Decimal("0")
        quantity = held if intent.quantity == "ALL" else intent.quantity
        if quantity <= 0:
            return reject(f"Satılacak {intent.symbol} yok")
    if rules is not None:
        quantity = rules.floor_quantity(quantity)
    else:
        quantity = quantity.quantize(DEFAULT_QTY_STEP, rounding=ROUND_DOWN)
    if quantity <= 0:
        return reject("Miktar işlem adımına yuvarlanınca sıfır oldu")

    trial = copy.deepcopy(portfolio)
    try:
        if rules is not None:
            rules.check(quantity, fill)
        if config.risk is not None:
            quantity, fill = config.risk.check(intent.symbol, quantity, fill)
        if intent.side == BUY:
            trial.buy(intent.symbol, quantity, fill, timestamp=bar.timestamp)
            if config.risk is not None:
                config.risk.check_after_buy(trial, intent.symbol, fill)
        else:
            trial.sell(intent.symbol, quantity, fill, timestamp=bar.timestamp)
    except TradeError as exc:
        return reject(str(exc))
    return trial


# --- rapor -------------------------------------------------------------------


def format_report(result: BacktestResult, benchmark: BacktestResult | None = None) -> str:
    m, c = result.metrics, result.config
    pct = lambda x: "—" if x is None else f"{x * 100:.2f}%"
    money = lambda x: f"{x:,.2f} {c.quote}"
    lines = [
        f"Strateji           : {result.strategy}",
        f"Dönem              : {m.start:%Y-%m-%d %H:%M} → {m.end:%Y-%m-%d %H:%M} ({m.bars} bar)",
        f"Ayarlar            : komisyon %{c.fees.taker_rate * 100}, kayma {c.slippage_bps} bps, "
        f"yürütme {c.execution}, işlem kuralları {'açık' if c.rules else 'kapalı'}, "
        f"risk {'açık' if c.risk else 'kapalı'}",
        f"Başlangıç / bitiş  : {money(m.initial_equity)} → {money(m.final_equity)}",
        f"Toplam getiri      : {pct(m.total_return)}",
        f"En büyük düşüş     : {pct(m.max_drawdown)}",
        f"İşlem (al/sat)     : {m.trades} ({m.buys}/{m.sells})",
        f"Kazanan satış oranı: {pct(m.win_rate)}",
        f"Gerçekleşen K/Z    : {money(m.realized_pnl)}",
        f"Ödenen komisyon    : {money(m.total_fees)} (başlangıcın {pct(m.fee_ratio)})",
        f"Reddedilen öneri   : {len(result.rejections)}",
    ]
    if benchmark is not None:
        b = benchmark.metrics
        lines += [
            f"Kıyas ({benchmark.strategy}) getiri: {pct(b.total_return)}, "
            f"en büyük düşüş {pct(b.max_drawdown)}",
            f"Kıyasa göre fark   : {pct(m.total_return - b.total_return)}",
        ]
    if result.rejections:
        lines.append("İlk reddedilenler:")
        for r in result.rejections[:5]:
            lines.append(f"  {r.timestamp:%Y-%m-%d %H:%M} {r.intent.side} {r.intent.symbol}: {r.reason}")
    lines.append("Not: geçmiş sonuç gelecekteki getiriyi göstermez.")
    return "\n".join(lines)


# --- komut satırı ------------------------------------------------------------


def main(argv=None) -> None:
    from .klines import load_bars
    from .prices import SAMPLE_CSV

    parser = argparse.ArgumentParser(
        prog="python -m jev.backtest",
        description="Çevrimdışı backtest. Gerçek borsaya bağlanmaz, emir göndermez.")
    parser.add_argument("--prices", nargs="+", default=[str(SAMPLE_CSV)],
                        help="Basit CSV (timestamp,symbol,close) ya da --kline-symbols ile "
                             "Binance kline CSV dosyaları")
    parser.add_argument("--kline-symbols", nargs="+",
                        help="Her kline dosyasının sembolü (aynı sırada)")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--strategy", choices=("sma", "al-tut"), default="sma")
    parser.add_argument("--fast", type=int, default=10)
    parser.add_argument("--slow", type=int, default=30)
    parser.add_argument("--fraction", default="0.95", help="Alışta kullanılacak nakit oranı")
    parser.add_argument("--cash", default="10000")
    parser.add_argument("--taker-rate", default="0.001")
    parser.add_argument("--slippage-bps", default="5")
    parser.add_argument("--rules", type=Path, help="exchangeInfo JSON (örnek: data/exchange_info_sample.json)")
    parser.add_argument("--max-trade-notional", help="Örnek risk: işlem başına azami tutar")
    parser.add_argument("--same-bar", action="store_true",
                        help="Aynı bar fiyatıyla işlem (geleceği görme hatası; yalnızca kıyas için)")
    args = parser.parse_args(argv)

    try:
        bars = load_bars(args.prices, kline_symbols=args.kline_symbols)
        config = BacktestConfig(
            initial_cash=D(args.cash),
            fees=FeeSchedule(taker_rate=args.taker_rate, maker_rate=args.taker_rate),
            slippage_bps=D(args.slippage_bps),
            rules=ExchangeRules.load(args.rules) if args.rules else None,
            risk=RiskLimits(max_trade_notional=args.max_trade_notional)
            if args.max_trade_notional else None,
            execution="same_bar" if args.same_bar else "next_bar",
        )
        strategy = (SmaCross(args.symbol, args.fast, args.slow, args.fraction)
                    if args.strategy == "sma" else BuyAndHold(args.symbol, args.fraction))
        result = run_backtest(bars, strategy, config)
        benchmark = None
        if args.strategy != "al-tut":
            benchmark = run_backtest(bars, BuyAndHold(args.symbol, args.fraction), config)
    except (ValueError, OSError, TradeError) as exc:
        parser.exit(1, f"Hata: {exc}\n")
    print(format_report(result, benchmark))


if __name__ == "__main__":
    main()
