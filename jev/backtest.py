"""Geriye dönük test (backtest) motoru — yalnızca sanal, ağ bağlantısı yok.

Her bar (zaman damgası = barın kapanışı) için sırasıyla:

1. **Koruyucu çıkışlar:** Önceden kurulmuş zarar durdur / kâr al seviyeleri
   barın açılış, yüksek ve düşük fiyatına göre kontrol edilir. Açılış seviyenin
   ötesindeyse (fiyat boşluğu) işlem açılıştan olur. Aynı barda iki seviye de
   değmişse hangisinin önce değdiği bilinemeyeceği için temkinli varsayımla
   zarar durdur uygulanır.
2. **Bekleyen piyasa emirleri:** Önceki barın kapanışında verilen öneriler bu
   barın açılış fiyatıyla (açılış yoksa kapanışla) gerçekleşir. Strateji barın
   kapanışını gördükten sonra karar verdiği için aynı barın fiyatından işlem
   yapması geleceği görmek olurdu; `execution="same_bar"` yalnızca kıyas içindir.
3. **Limit emirler:** Alış limiti barın düşüğü limite inerse, satış limiti
   barın yükseği limite çıkarsa gerçekleşir; açılış limitten iyiyse açılıştan.
   Maker komisyonu uygulanır, kayma uygulanmaz. Süresi dolan emir reddedilir.
4. Stratejiye salt okunur görünüm verilir, yeni öneriler alınır.
5. Portföy son bilinen fiyatlarla değerlenir, varlık eğrisine eklenir.

Her gerçekleşme için: kayma (piyasa emri ve zarar durdur), Binance işlem
kuralları (miktar aşağı yuvarlanır), likidite sınırı ve `RiskLimits` uygulanır.
Alış sonrası risk kontrolleri deneme kopyasında yapılır; geçmezse portföy
değişmez. Reddedilen her öneri nedeniyle kaydedilir.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from typing import Sequence

from .exchange_rules import ExchangeRules
from .fees import D, FeeSchedule
from .metrics import Metrics, compute_metrics
from .portfolio import Portfolio, Trade, TradeError
from .risk import RiskLimits
from .journal import Decision, DecisionJournal
from .strategy import (BUY, LIMIT, SELL, Bar, BuyAndHold, Hold, OrderIntent, PortfolioView,
                       SmaCross, Strategy)

BPS = Decimal("10000")
# Kural dosyası yoksa Binance'in 8 ondalık hassasiyeti varsayılır.
DEFAULT_QTY_STEP = Decimal("0.00000001")

# Gerçekleşme türleri
K_MARKET, K_LIMIT, K_STOP, K_TAKE = "PIYASA", "LIMIT", "ZARAR_DURDUR", "KAR_AL"


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: Decimal = Decimal("10000")
    fees: FeeSchedule = field(default_factory=FeeSchedule)
    slippage_bps: Decimal = Decimal("0")
    rules: ExchangeRules | None = None
    risk: RiskLimits | None = None
    execution: str = "next_bar"  # ya da "same_bar"
    quote: str = "USDT"
    # Bir işlemin, barın karşı para hacminin en fazla bu payı olmasına izin ver
    # (0.01 = %1). Hacim bilinmiyorsa uygulanmaz.
    max_volume_share: Decimal | None = None

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
        if self.max_volume_share is not None:
            share = D(self.max_volume_share)
            if not share.is_finite() or not 0 < share <= 1:
                raise ValueError("max_volume_share 0 ile 1 arasında olmalı (0 hariç)")
            object.__setattr__(self, "max_volume_share", share)


@dataclass(frozen=True)
class Rejection:
    timestamp: datetime
    intent: OrderIntent
    reason: str
    kind: str = K_MARKET


@dataclass(frozen=True)
class FillNote:
    """portfolio.trades ile aynı sırada: işlemin türü ve gerekçesi."""
    kind: str
    reason: str


@dataclass(frozen=True)
class ProtectiveExit:
    stop_loss: Decimal | None
    take_profit: Decimal | None


@dataclass
class BacktestResult:
    strategy: str
    config: BacktestConfig
    portfolio: Portfolio
    equity_curve: list[tuple[datetime, Decimal]]
    rejections: list[Rejection]
    metrics: Metrics
    notes: list[FillNote] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)  # stratejinin tüm kararları

    @property
    def trades(self) -> list[Trade]:
        return self.portfolio.trades


class _Engine:
    def __init__(self, config: BacktestConfig):
        self.c = config
        self.portfolio = Portfolio(cash=config.initial_cash, fees=config.fees, quote=config.quote)
        self.rejections: list[Rejection] = []
        self.notes: list[FillNote] = []
        self.exits: dict[str, ProtectiveExit] = {}
        self.working: list[list] = []  # [intent, kalan_bar]
        # Gerçekleşen öneri nesneleri (id() değil: nesneler diske kaydedilip
        # geri yüklenince id değişir, nesne bağları korunur)
        self.filled: list[OrderIntent] = []

    # --- tek bir gerçekleşme --------------------------------------------------

    def fill(self, intent: OrderIntent, bar: Bar, price: Decimal, *, kind: str, taker: bool,
             slippage: bool, apply_risk: bool = True, check_liquidity: bool = True) -> bool:
        try:
            self.portfolio = self._try_fill(intent, bar, price, taker=taker, slippage=slippage,
                                            apply_risk=apply_risk, check_liquidity=check_liquidity)
        except TradeError as exc:
            self.rejections.append(Rejection(bar.timestamp, intent, str(exc), kind))
            return False
        self.notes.append(FillNote(kind, intent.reason))
        self.filled.append(intent)
        if intent.side == BUY and (intent.stop_loss or intent.take_profit):
            sl, tp = intent.stop_loss, intent.take_profit
            if self.c.rules is not None:
                # Binance'te tetik/limit fiyatı tick katı olmalı. Yukarı yuvarlama
                # temkinli: zarar durdur biraz erken, kâr al biraz geç tetiklenir.
                r = self.c.rules[intent.symbol]
                sl = r.round_price(sl, up=True) if sl is not None else None
                tp = r.round_price(tp, up=True) if tp is not None else None
            self.exits[intent.symbol] = ProtectiveExit(sl, tp)
        for symbol in list(self.exits):
            if symbol not in self.portfolio.positions:
                del self.exits[symbol]
        return True

    def _try_fill(self, intent, bar, price, *, taker, slippage, apply_risk, check_liquidity):
        c, portfolio = self.c, self.portfolio
        fill = D(price)
        if slippage:
            slip = c.slippage_bps / BPS
            fill = fill * (1 + slip) if intent.side == BUY else fill * (1 - slip)
        rules = c.rules[intent.symbol] if c.rules is not None else None
        rate = c.fees.taker_rate if taker else c.fees.maker_rate

        if intent.side == BUY:
            if intent.quote_amount is not None:
                budget = min(intent.quote_amount, portfolio.cash)
                quantity = budget / (fill * (1 + rate))  # komisyon dahil bütçeye sığan
            else:
                quantity = intent.quantity
        else:
            pos = portfolio.positions.get(intent.symbol)
            held = pos.quantity if pos else Decimal("0")
            quantity = held if intent.quantity == "ALL" else intent.quantity
            if quantity <= 0:
                raise TradeError(f"Satılacak {intent.symbol} yok")
        quantity = (rules.floor_quantity(quantity, market=intent.order_type != LIMIT)
                    if rules is not None
                    else quantity.quantize(DEFAULT_QTY_STEP, rounding=ROUND_DOWN))
        if quantity <= 0:
            raise TradeError("Miktar işlem adımına yuvarlanınca sıfır oldu")

        if rules is not None:
            rules.check(quantity, fill, market=intent.order_type != LIMIT,
                        check_price_filter=False)
        if check_liquidity and c.max_volume_share is not None:
            volume = bar.quote_volume(intent.symbol)
            if volume is not None and quantity * fill > volume * c.max_volume_share:
                raise TradeError(
                    f"Likidite: tutar {quantity * fill:.2f}, barın {volume:.2f} hacminin "
                    f"%{c.max_volume_share * 100} sınırını aşıyor")
        if apply_risk and c.risk is not None and intent.side == BUY:
            # Risk limitleri yeni risk almayı sınırlar. Satış riski azaltır; işlem başına
            # tutar sınırı satışa uygulanırsa değeri artmış bir pozisyon hiç satılamaz.
            quantity, fill = c.risk.check(intent.symbol, quantity, fill)

        trial = copy.deepcopy(portfolio)
        if intent.side == BUY:
            trial.buy(intent.symbol, quantity, fill, taker=taker, timestamp=bar.timestamp)
            if apply_risk and c.risk is not None:
                from .market import PriceObservation
                now = bar.timestamp.astimezone(timezone.utc)
                daily_loss = sum((max(-t.realized_pnl, Decimal(0))
                                  for t in portfolio.trades
                                  if t.timestamp.astimezone(timezone.utc).date() == now.date()),
                                 Decimal(0))
                # next_bar yürütmesinde diğer sembollerin kapanışını kullanma:
                # henüz gerçekleşmemiş kapanışlar geleceğe bakmak olurdu.
                marks = {symbol: PriceObservation(symbol,
                            bar.prices[symbol] if c.execution == "same_bar" else bar.open(symbol),
                            bar.timestamp, bar.timestamp, source="backtest bar", average_minutes=0)
                         for symbol in bar.prices}
                c.risk.check_after_buy(trial, intent.symbol, fill, now=now,
                                       market_prices=marks, daily_loss=daily_loss)
        else:
            trial.sell(intent.symbol, quantity, fill, taker=taker, timestamp=bar.timestamp)
        return trial

    # --- bar adımları ---------------------------------------------------------

    def check_exits(self, bar: Bar) -> None:
        for symbol, ex in list(self.exits.items()):
            if symbol not in bar.prices or symbol not in self.portfolio.positions:
                continue
            o, h, l = bar.open(symbol), bar.high(symbol), bar.low(symbol)
            sl, tp = ex.stop_loss, ex.take_profit
            if sl is not None and o <= sl:
                args = (o, K_STOP, f"zarar durdur {sl}: açılış boşluğu")
            elif tp is not None and o >= tp:
                args = (o, K_TAKE, f"kâr al {tp}: açılış boşluğu")
            elif sl is not None and l <= sl:
                args = (sl, K_STOP, f"zarar durdur {sl}")
            elif tp is not None and h >= tp:
                args = (tp, K_TAKE, f"kâr al {tp}")
            else:
                continue
            price, kind, reason = args
            intent = OrderIntent(symbol, SELL, quantity="ALL", reason=reason)
            # Koruyucu çıkış: zarar durdur piyasa emri gibi (taker + kayma),
            # kâr al limit emri gibi (maker, kaymasız). Risk ve likidite
            # sınırları çıkışı engellemez; işlem kuralları uygulanır.
            self.fill(intent, bar, price, kind=kind, taker=kind == K_STOP,
                      slippage=kind == K_STOP, apply_risk=False, check_liquidity=False)

    def check_limits(self, bar: Bar) -> None:
        still = []
        for intent, remaining in self.working:
            s, limit = intent.symbol, intent.limit_price
            touched = False
            if s in bar.prices:
                if intent.side == BUY and bar.low(s) <= limit:
                    touched, price = True, min(bar.open(s), limit)
                elif intent.side == SELL and bar.high(s) >= limit:
                    touched, price = True, max(bar.open(s), limit)
            if touched:
                self.fill(intent, bar, price, kind=K_LIMIT, taker=False, slippage=False)
            elif remaining > 1:
                still.append([intent, remaining - 1])
            else:
                self.rejections.append(Rejection(bar.timestamp, intent,
                                                 "Limit emrin süresi doldu", K_LIMIT))
        self.working = still

    def place_limit(self, intent: OrderIntent, bar: Bar) -> None:
        try:
            if self.c.rules is not None:
                self.c.rules[intent.symbol].check_price(intent.limit_price)
        except TradeError as exc:
            self.rejections.append(Rejection(bar.timestamp, intent, str(exc), K_LIMIT))
            return
        self.working.append([intent, intent.good_for_bars])


class Simulator:
    """Backtest ve canlı sanal işlemin ortak motoru: barları tek tek işler.

    `run_backtest` tüm barları bir seferde verir; canlı çalıştırıcı (`jev.live`)
    her saat yeni kapanan barı verir ve nesneyi diske kaydedip sonra devam eder.
    Aynı bar dizisi için ikisi aynı işlemleri üretir.
    """

    def __init__(self, strategy: Strategy, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()
        self.strategy = strategy
        self.source = getattr(strategy, "name", type(strategy).__name__)
        self.e = _Engine(self.config)
        self.last_prices: dict[str, Decimal] = {}
        self.equity_curve: list[tuple[datetime, Decimal]] = []
        self.pending: list[OrderIntent] = []
        self.issued: list[tuple[OrderIntent | Hold, Decision]] = []
        self.closes: dict[str, list[tuple[datetime, Decimal]]] = {}
        self.last_timestamp: datetime | None = None

    @property
    def portfolio(self) -> Portfolio:
        return self.e.portfolio

    def _accept(self, bar: Bar) -> None:
        if self.last_timestamp is not None and bar.timestamp <= self.last_timestamp:
            raise ValueError("Barlar zaman sırasına göre ve tekrarsız olmalı")
        self.last_timestamp = bar.timestamp
        self.last_prices.update(bar.prices)
        for s, p in bar.prices.items():
            self.closes.setdefault(s, []).append((bar.timestamp, p))

    def _view(self) -> PortfolioView:
        e = self.e
        return PortfolioView(
            cash=e.portfolio.cash,
            positions={s: p.quantity for s, p in e.portfolio.positions.items()},
            equity=e.portfolio.equity(self.last_prices),
            open_orders=tuple(intent for intent, _ in e.working),
        )

    def step(self, bar: Bar) -> None:
        """Bir barı işler: çıkışlar, bekleyen emirler, limitler, strateji kararı."""
        e, config = self.e, self.config
        self._accept(bar)
        e.check_exits(bar)
        for intent in self.pending:
            price = bar.open(intent.symbol) if intent.symbol in bar.prices else None
            if price is None:
                e.rejections.append(Rejection(bar.timestamp, intent,
                                              f"{intent.symbol} için bu barda fiyat yok"))
                continue
            e.fill(intent, bar, price, kind=K_MARKET, taker=True, slippage=True)
        self.pending = []
        e.check_limits(bar)

        outputs = list(self.strategy.on_bar(bar, self._view()) or [])
        for item in outputs:
            if not isinstance(item, (OrderIntent, Hold)):
                raise TypeError(f"Strateji OrderIntent / Hold dışında değer döndürdü: {item!r}")
            if item.symbol in bar.prices:
                self.issued.append((item, Decision(
                    bar.timestamp, item.symbol, "HOLD" if isinstance(item, Hold) else item.side,
                    bar.prices[item.symbol], item.confidence, self.source, item.reason)))
        for intent in (i for i in outputs if isinstance(i, OrderIntent)):
            if intent.order_type == LIMIT:
                e.place_limit(intent, bar)  # sonraki bardan itibaren geçerli
            elif config.execution == "same_bar":
                if intent.symbol in bar.prices:
                    e.fill(intent, bar, bar.prices[intent.symbol], kind=K_MARKET, taker=True,
                           slippage=True)
                else:
                    e.rejections.append(Rejection(bar.timestamp, intent,
                                                  f"{intent.symbol} için bu barda fiyat yok"))
            else:
                self.pending.append(intent)

        self.equity_curve.append((bar.timestamp, e.portfolio.equity(self.last_prices)))

    def observe(self, bar: Bar) -> None:
        """Barı yalnızca stratejiye gösterir (ısınma / eski veri): işlem yapılmaz,
        kararlar atılır. Portföy değerlemesi güncellenir."""
        self._accept(bar)
        self.strategy.on_bar(bar, self._view())
        self.equity_curve.append((bar.timestamp, self.e.portfolio.equity(self.last_prices)))

    def finish(self) -> None:
        """Veri sonu: bekleyen ve açık limit emirleri reddedilmiş say (yalnızca backtest)."""
        end = self.last_timestamp
        for intent in self.pending:
            self.e.rejections.append(Rejection(end, intent, "Veri bitti; öneri gerçekleştirilemedi"))
        self.pending = []
        for intent, _ in self.e.working:
            self.e.rejections.append(Rejection(end, intent, "Veri bitti; limit emir açık kaldı",
                                               K_LIMIT))
        self.e.working = []

    def decisions(self) -> list[Decision]:
        """Tüm kararlar, güncel durumlarıyla ("bekliyor": henüz sonuçlanmadı)."""
        filled = {id(x) for x in self.e.filled}
        reasons = {id(r.intent): r.reason for r in self.e.rejections}
        out = []
        for item, d in self.issued:
            status = ("bekle" if isinstance(item, Hold)
                      else "gerçekleşti" if id(item) in filled
                      else f"reddedildi: {reasons[id(item)]}" if id(item) in reasons
                      else "bekliyor")
            out.append(Decision(d.timestamp, d.symbol, d.action, d.price, d.confidence,
                                d.source, d.reason, status))
        return out

    def result(self) -> BacktestResult:
        if not self.equity_curve:
            raise ValueError("Henüz işlenmiş bar yok")
        return BacktestResult(
            decisions=self.decisions(),
            strategy=self.source,
            config=self.config,
            portfolio=self.e.portfolio,
            equity_curve=list(self.equity_curve),
            rejections=list(self.e.rejections),
            metrics=compute_metrics(self.equity_curve, self.e.portfolio.trades,
                                    self.config.initial_cash),
            notes=list(self.e.notes),
        )


def run_backtest(bars: Sequence[Bar], strategy: Strategy, config: BacktestConfig | None = None,
                 journal: DecisionJournal | None = None) -> BacktestResult:
    if not bars:
        raise ValueError("Backtest için en az bir bar gerekli")
    if any(b.timestamp >= c.timestamp for b, c in zip(bars, bars[1:])):
        raise ValueError("Barlar zaman sırasına göre ve tekrarsız olmalı")
    sim = Simulator(strategy, config)
    for bar in bars:
        sim.step(bar)
    sim.finish()
    result = sim.result()
    if journal is not None:
        for d in result.decisions:
            journal.record(d)
    return result


# --- rapor ve dışa aktarma ----------------------------------------------------


def format_report(result: BacktestResult, benchmark: BacktestResult | None = None) -> str:
    m, c = result.metrics, result.config
    pct = lambda x: "—" if x is None else f"{x * 100:.2f}%"
    money = lambda x: f"{x:,.2f} {c.quote}"
    kinds: dict[str, int] = {}
    for n in result.notes:
        kinds[n.kind] = kinds.get(n.kind, 0) + 1
    lines = [
        f"Strateji           : {result.strategy}",
        f"Dönem              : {m.start:%Y-%m-%d %H:%M} → {m.end:%Y-%m-%d %H:%M} ({m.bars} bar)",
        f"Ayarlar            : taker %{c.fees.taker_rate * 100} / maker %{c.fees.maker_rate * 100}, "
        f"kayma {c.slippage_bps} bps, yürütme {c.execution}, "
        f"işlem kuralları {'açık' if c.rules else 'kapalı'}, risk {'açık' if c.risk else 'kapalı'}, "
        f"likidite sınırı {pct(c.max_volume_share) if c.max_volume_share else 'kapalı'}",
        f"Başlangıç / bitiş  : {money(m.initial_equity)} → {money(m.final_equity)}",
        f"Toplam getiri      : {pct(m.total_return)}",
        f"En büyük düşüş     : {pct(m.max_drawdown)}",
        f"İşlem (al/sat)     : {m.trades} ({m.buys}/{m.sells})"
        + (f" — {', '.join(f'{k.lower()} {v}' for k, v in sorted(kinds.items()))}" if kinds else ""),
        f"Kazanan satış oranı: {pct(m.win_rate)}",
        f"Gerçekleşen K/Z    : {money(m.realized_pnl)}",
        f"Açık pozisyon K/Z  : {money(m.final_equity - m.initial_equity - m.realized_pnl)}"
        + (f" ({', '.join(sorted(result.portfolio.positions))} açık)" if result.portfolio.positions else ""),
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


def write_results(result: BacktestResult, out_dir: str | Path) -> list[Path]:
    """İşlemler, varlık eğrisi, redler (CSV) ve özet (JSON) dosyalarını yazar."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []

    def write_csv(name, header, rows):
        path = out / name
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        paths.append(path)

    write_csv("islemler.csv",
              ["zaman", "sembol", "yon", "tur", "miktar", "fiyat", "komisyon",
               "gerceklesen_kz", "gerekce"],
              [(t.timestamp.isoformat(), t.symbol, t.side, n.kind, t.quantity, t.price, t.fee,
                t.realized_pnl, n.reason) for t, n in zip(result.trades, result.notes)])
    write_csv("varlik_egrisi.csv", ["zaman", "toplam_varlik"],
              [(ts.isoformat(), v) for ts, v in result.equity_curve])
    write_csv("redler.csv", ["zaman", "sembol", "yon", "tur", "neden", "oneri_gerekcesi"],
              [(r.timestamp.isoformat(), r.intent.symbol, r.intent.side, r.kind, r.reason,
                r.intent.reason) for r in result.rejections])

    def plain(v):
        if isinstance(v, Decimal):
            return str(v)
        if isinstance(v, datetime):
            return v.isoformat()
        return v

    c = result.config
    summary = {
        "strateji": result.strategy,
        "metrikler": {k: plain(v) for k, v in asdict(result.metrics).items()},
        "ayarlar": {
            "baslangic_nakit": str(c.initial_cash), "taker": str(c.fees.taker_rate),
            "maker": str(c.fees.maker_rate), "kayma_bps": str(c.slippage_bps),
            "yurutme": c.execution, "islem_kurallari": c.rules is not None,
            "risk": c.risk is not None,
            "likidite_payi": str(c.max_volume_share) if c.max_volume_share else None,
        },
        "reddedilen": len(result.rejections),
    }
    path = out / "ozet.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    paths.append(path)
    return paths


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
    parser.add_argument("--stop-loss-pct", help="SMA alışında zarar durdur, ör. 0.05 = %%5 aşağı")
    parser.add_argument("--take-profit-pct", help="SMA alışında kâr al, ör. 0.10 = %%10 yukarı")
    parser.add_argument("--vol-target",
                        help="Oynaklığa göre pozisyon: hedef günlük oynaklık, ör. 0.02 = %%2 "
                             "(verilirse --fraction yerine kullanılır)")
    parser.add_argument("--vol-window", type=int, default=72, help="Oynaklık penceresi (bar)")
    parser.add_argument("--bars-per-day", type=int, default=24,
                        help="Günlük bar sayısı (1s veri için 24)")
    parser.add_argument("--cash", default="10000")
    parser.add_argument("--taker-rate", default="0.001")
    parser.add_argument("--maker-rate", default="0.001")
    parser.add_argument("--slippage-bps", default="5")
    parser.add_argument("--max-volume-share",
                        help="İşlem başına bar hacminin azami payı, ör. 0.01 = %%1 (kline verisiyle)")
    parser.add_argument("--rules", type=Path, help="exchangeInfo JSON (örnek: data/exchange_info_sample.json)")
    parser.add_argument("--max-trade-notional", help="Örnek risk: işlem başına azami tutar")
    parser.add_argument("--same-bar", action="store_true",
                        help="Aynı bar fiyatıyla işlem (geleceği görme hatası; yalnızca kıyas için)")
    parser.add_argument("--out", type=Path, help="Sonuç dosyalarının yazılacağı klasör")
    parser.add_argument("--calibration", action="store_true",
                        help="Karar isabeti ve güven kalibrasyonu raporunu da yazdır")
    parser.add_argument("--decision-horizon", type=int, default=24,
                        help="Kararın haklı olup olmadığına kaç bar sonra bakılsın (varsayılan 24)")
    parser.add_argument("--decision-threshold",
                        help="Haklı sayılma eşiği; varsayılan bir al-sat turunun maliyeti "
                             "(2 × komisyon + 2 × kayma)")
    parser.add_argument("--journal", type=Path, help="Kararları bu JSONL dosyasına ekle")
    args = parser.parse_args(argv)

    try:
        bars = load_bars(args.prices, kline_symbols=args.kline_symbols)
        config = BacktestConfig(
            initial_cash=D(args.cash),
            fees=FeeSchedule(taker_rate=args.taker_rate, maker_rate=args.maker_rate),
            slippage_bps=D(args.slippage_bps),
            rules=ExchangeRules.load(args.rules) if args.rules else None,
            risk=RiskLimits(max_trade_notional=args.max_trade_notional)
            if args.max_trade_notional else None,
            execution="same_bar" if args.same_bar else "next_bar",
            max_volume_share=D(args.max_volume_share) if args.max_volume_share else None,
        )
        sizer = None
        if args.vol_target:
            from .sizing import VolatilityTargetSizer
            sizer = VolatilityTargetSizer(args.vol_target, args.vol_window, args.bars_per_day,
                                          max_fraction=args.fraction)
        strategy = (SmaCross(args.symbol, args.fast, args.slow, args.fraction,
                             stop_loss_pct=args.stop_loss_pct, take_profit_pct=args.take_profit_pct,
                             sizer=sizer)
                    if args.strategy == "sma" else BuyAndHold(args.symbol, args.fraction))
        journal = DecisionJournal(args.journal) if args.journal else None
        result = run_backtest(bars, strategy, config, journal=journal)
        benchmark = None
        if args.strategy != "al-tut":
            benchmark = run_backtest(bars, BuyAndHold(args.symbol, args.fraction), config)
        written = write_results(result, args.out) if args.out else []
        calib_text = None
        if args.calibration or args.out:
            from .journal import calibration, closes_from_bars, evaluate, format_calibration, \
                write_outcomes_csv
            threshold = (D(args.decision_threshold) if args.decision_threshold is not None
                         else 2 * config.fees.taker_rate + 2 * config.slippage_bps / BPS)
            outcomes = evaluate(result.decisions, closes_from_bars(bars), args.decision_horizon,
                                threshold)
            if args.out:
                written.append(write_outcomes_csv(outcomes, args.out / "kararlar.csv"))
            if args.calibration:
                calib_text = format_calibration(calibration(outcomes), args.decision_horizon,
                                                threshold)
    except (ValueError, OSError, TradeError) as exc:
        parser.exit(1, f"Hata: {exc}\n")
    print(format_report(result, benchmark))
    if calib_text:
        print()
        print(calib_text)
    for path in written:
        print(f"Yazıldı: {path}")


if __name__ == "__main__":
    main()
