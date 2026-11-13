"""Strateji sağlamlık testi: ayar ızgarası, dönemlere bölme ve ileriye dönük seçim.

Soru: Canlı bottaki SMA kesişim ayarı gerçek bir şey yakalıyor mu, yoksa geçmişe
tesadüfen mi uymuş? Üç bakış:

1. **Komşuluk**: Ayarlar biraz değişince sonuç çöküyor mu? Sağlam bir ayar,
   iyi sonuç veren geniş bir bölgenin içinde olmalı, tek bir sivri tepe değil.
2. **Dönemler**: Getiri her çeyrekte mi geliyor, yoksa tek bir dönem mi taşıyor?
3. **İleriye dönük seçim (walk-forward)**: Her çeyrek başında "geçen çeyreğin en
   iyisi" seçilip bir sonraki çeyrekte denenir. Geçmişte en iyiyi seçmek
   gelecekte de işe yarıyorsa sinyal vardır; yaramıyorsa ızgaradaki en iyi sonuç
   tesadüftür.

Karşılaştırmalar: nakit (0), eşit ağırlıklı al-tut, ve stratejinin ortalama
yatırım oranıyla ölçeklenmiş al-tut (strateji çoğu zaman nakitteyse adil kıyas).

İki mod:
- **sinyal**: risk limitleri yok, sembol başına sermayenin eşit payı. Sinyalin
  kendisini ölçer.
- **canlı**: Hostinger'daki botun ayarlarıyla (500 USDT, 50/150/200 limitleri).

Gelecekteki getiriyi göstermez; komisyon ve kayma dahildir.
"""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Sequence

from .backtest import Simulator
from .klines import load_bars
from .live import build_config, build_strategy
from .metrics import max_drawdown
from .strategy import Bar

FASTS = (6, 12, 24, 48)
SLOWS = (48, 96, 168, 240)

LIVE = {"interval": "1h", "strategy": "sma", "fast": 24, "slow": 96, "fraction": "0.95",
        "vol_target": "0.01", "vol_window": 72, "stop_loss_pct": None, "take_profit_pct": None,
        "cash": "500", "taker_rate": "0.001", "slippage_bps": "5", "max_volume_share": "0.01",
        "max_trade_notional": "50", "max_position_notional": "150", "min_cash_reserve": "200"}


def signal_settings(symbols, fast, slow, vol_target="0.01", rules=None, **kw) -> dict:
    s = dict(LIVE, symbols=list(symbols), fast=fast, slow=slow, cash="10000",
             fraction=str((Decimal("0.95") / len(symbols)).quantize(Decimal("0.0001"))),
             vol_target=vol_target, max_trade_notional=None, max_position_notional=None,
             min_cash_reserve=None, rules=rules)
    s.update(kw)
    return s


def live_settings(symbols, rules=None, **kw) -> dict:
    s = dict(LIVE, symbols=list(symbols), rules=rules)
    s.update(kw)
    return s


def quarter(ts: datetime) -> str:
    return f"{ts.year}-Ç{(ts.month - 1) // 3 + 1}"


@dataclass
class Run:
    label: str
    settings: dict
    equity: list[tuple[datetime, Decimal]]
    exposure: Decimal                 # ortalama (pozisyon değeri / toplam varlık)
    trades: int
    fees: Decimal
    initial: Decimal
    period_returns: dict[str, Decimal] = field(default_factory=dict)

    @property
    def total_return(self) -> Decimal:
        return self.equity[-1][1] / self.initial - 1

    @property
    def max_dd(self) -> Decimal:
        return max_drawdown([v for _, v in self.equity])


def period_returns(equity: Sequence[tuple[datetime, Decimal]], initial: Decimal
                   ) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    start, current = initial, None
    for ts, v in equity:
        q = quarter(ts)
        if current is not None and q != current:
            out[current] = last / start - 1
            start = last
        current, last = q, v
    if current is not None:
        out[current] = last / start - 1
    return out


def run(bars: Sequence[Bar], settings: dict, label: str = "") -> Run:
    sim = Simulator(build_strategy(settings), build_config(settings))
    exp_sum, n = Decimal(0), 0
    for bar in bars:
        sim.step(bar)
        equity = sim.equity_curve[-1][1]
        if equity > 0:
            exp_sum += (equity - sim.portfolio.cash) / equity
            n += 1
    sim.finish()
    initial = sim.config.initial_cash
    r = Run(label or f"{settings['fast']}/{settings['slow']}", settings, list(sim.equity_curve),
            exp_sum / n if n else Decimal(0), len(sim.portfolio.trades),
            sum((t.fee for t in sim.portfolio.trades), Decimal(0)), initial)
    r.period_returns = period_returns(r.equity, initial)
    return r


def buy_and_hold(bars: Sequence[Bar], symbols: Sequence[str]) -> list[tuple[datetime, Decimal]]:
    """Eşit ağırlıklı al-tut, masrafsız: 1 birim sermaye ilk kapanışta bölünür."""
    first = {s: bars[0].prices[s] for s in symbols}
    return [(b.timestamp, sum(b.prices[s] / first[s] for s in symbols) / len(symbols))
            for b in bars]


def walk_forward(runs: Sequence[Run], periods: Sequence[str]) -> list[tuple[str, str, Decimal]]:
    """Her dönem için önceki dönemin en iyisini seç; o dönemdeki getirisini döndür."""
    out = []
    for prev, cur in zip(periods, periods[1:]):
        best = max(runs, key=lambda r: r.period_returns.get(prev, Decimal("-1")))
        out.append((cur, best.label, best.period_returns.get(cur, Decimal(0))))
    return out


def _pct(x: Decimal | float | None, digits: int = 1) -> str:
    return "—" if x is None else f"{float(x) * 100:+.{digits}f}%"


def _share(x: Decimal, digits: int = 0) -> str:
    return f"%{float(x) * 100:.{digits}f}"


def _compound(xs) -> Decimal:
    total = Decimal(1)
    for x in xs:
        total *= 1 + x
    return total - 1


def analyse(bars: Sequence[Bar], symbols: Sequence[str], rules: str | None = None,
            fasts=FASTS, slows=SLOWS) -> dict:
    grid = [run(bars, signal_settings(symbols, f, s, rules=rules)) for f in fasts for s in slows
            if f < s]
    grid_novol = [run(bars, signal_settings(symbols, f, s, vol_target=None, rules=rules),
                      f"{f}/{s} sabit") for f in fasts for s in slows if f < s]
    live = run(bars, live_settings(symbols, rules=rules), "canlı ayar 24/96")
    costs = [run(bars, signal_settings(symbols, 24, 96, rules=rules, **kw), label)
             for label, kw in (("komisyon %0,075 (BNB)", {"taker_rate": "0.00075"}),
                               ("komisyon %0,1 (varsayılan)", {}),
                               ("kayma 10 bps", {"slippage_bps": "10"}),
                               ("kayma 20 bps", {"slippage_bps": "20"}))]
    bh = buy_and_hold(bars, symbols)
    bh_periods = period_returns(bh, Decimal(1))
    return {"grid": grid, "grid_novol": grid_novol, "live": live, "costs": costs, "bh": bh,
            "bh_periods": bh_periods, "periods": list(bh_periods), "symbols": list(symbols),
            "start": bars[0].timestamp, "end": bars[-1].timestamp, "bars": len(bars),
            "fasts": tuple(fasts), "slows": tuple(slows)}


def report(a: dict) -> str:
    grid, live, bh, periods = a["grid"], a["live"], a["bh"], a["periods"]
    bh_total = bh[-1][1] / bh[0][1] - 1
    bh_dd = max_drawdown([v for _, v in bh])
    ref = next(r for r in grid if r.label == "24/96")
    L = [f"# Strateji sağlamlık testi — {', '.join(a['symbols'])}",
         "",
         f"Veri: Binance 1 saatlik mumlar, {a['start']:%Y-%m-%d} → {a['end']:%Y-%m-%d} "
         f"({a['bars']} bar). Komisyon %0,1, kayma 5 bps, sonraki bar açılışında işlem.",
         "Geçmiş sonuç gelecekteki getiriyi göstermez.",
         "",
         "## 1. Özet",
         "",
         "| | Toplam getiri | En büyük düşüş | İşlem | Komisyon | Ort. yatırım oranı |",
         "|---|---|---|---|---|---|",
         f"| Sinyal 24/96 (limitsiz, oynaklık hedefli) | {_pct(ref.total_return)} | "
         f"{_pct(-ref.max_dd)} | {ref.trades} | {_share(ref.fees / ref.initial, 2)} | "
         f"{_share(ref.exposure)} |",
         f"| Canlı ayar (500 USDT, 50/150/200) | {_pct(live.total_return)} | "
         f"{_pct(-live.max_dd)} | {live.trades} | {_share(live.fees / live.initial, 2)} | "
         f"{_share(live.exposure)} |",
         f"| Eşit ağırlıklı al-tut (masrafsız) | {_pct(bh_total)} | {_pct(-bh_dd)} | — | — | "
         f"%100 |",
         f"| Al-tut × sinyalin yatırım oranı | {_pct(bh_total * ref.exposure)} | "
         f"{_pct(-bh_dd * ref.exposure)} | — | — | {_share(ref.exposure)} |",
         ""]

    # 2. ızgara
    fasts, slows = a["fasts"], a["slows"]
    by = {r.label: r for r in grid}
    L += ["## 2. Ayar ızgarası (sinyal modu, toplam getiri)", "",
          "Satır: hızlı ortalama (saat), sütun: yavaş ortalama (saat). Kalın: canlı ayar.", "",
          "| hızlı \\ yavaş | " + " | ".join(str(s) for s in slows) + " |",
          "|---|" + "---|" * len(slows)]
    for f in fasts:
        cells = []
        for s in slows:
            r = by.get(f"{f}/{s}")
            cell = "" if r is None else _pct(r.total_return)
            cells.append(f"**{cell}**" if (f, s) == (24, 96) else cell)
        L.append(f"| {f} | " + " | ".join(cells) + " |")
    rets = sorted((r.total_return for r in grid), reverse=True)
    rank = rets.index(ref.total_return) + 1
    positive = sum(1 for x in rets if x > 0)
    beat_scaled = sum(1 for r in grid if r.total_return > bh_total * r.exposure)
    nv = a["grid_novol"]
    L += ["",
          f"- 24/96, {len(grid)} ayar içinde **{rank}.** sırada. Ortanca ayar "
          f"{_pct(statistics.median(rets))}, en iyi {_pct(rets[0])}, en kötü {_pct(rets[-1])}.",
          f"- Ayarların {positive}/{len(grid)} tanesi kârda. {beat_scaled}/{len(grid)} tanesi "
          f"aynı yatırım oranlı al-tutu geçiyor.",
          f"- Oynaklık hedefi olmadan (sabit pay): ortanca "
          f"{_pct(statistics.median(r.total_return for r in nv))}, kârda olan "
          f"{sum(1 for r in nv if r.total_return > 0)}/{len(nv)}.",
          ""]

    # 3. dönemler
    wf = walk_forward(grid, periods)
    wf_by = {p: (lbl, x) for p, lbl, x in wf}
    best_in = {p: max(grid, key=lambda r: r.period_returns.get(p, Decimal(-1))) for p in periods}
    L += ["## 3. Çeyrek çeyrek", "",
          "| Çeyrek | Al-tut | Sinyal 24/96 | Canlı ayar | O çeyreğin en iyisi (sonradan) | "
          "İleriye dönük seçim (geçen çeyreğin en iyisi) |",
          "|---|---|---|---|---|---|"]
    for p in periods:
        b = best_in[p]
        w = wf_by.get(p)
        L.append(f"| {p} | {_pct(a['bh_periods'][p])} | {_pct(ref.period_returns.get(p))} | "
                 f"{_pct(live.period_returns.get(p), 2)} | {b.label}: {_pct(b.period_returns[p])} | "
                 + (f"{w[0]}: {_pct(w[1])}" if w else "— (ilk çeyrek)") + " |")
    wf_total = _compound(x for _, _, x in wf)
    ref_after = _compound(ref.period_returns.get(p, Decimal(0)) for p in periods[1:])
    med_after = statistics.median(_compound(r.period_returns.get(p, Decimal(0))
                                            for p in periods[1:]) for r in grid)
    up_q = sum(1 for p in periods if ref.period_returns.get(p, 0) > 0)
    L += ["",
          f"- 24/96 {up_q}/{len(periods)} çeyrekte kârda.",
          f"- İlk çeyrek hariç birleşik getiri: ileriye dönük seçim {_pct(wf_total)}, "
          f"sabit 24/96 {_pct(ref_after)}, ızgara ortancası {_pct(med_after)}.",
          "  İleriye dönük seçim ortancadan belirgin iyi değilse, ızgaradaki en iyi ayarı "
          "seçmek geleceğe taşınmıyor demektir.",
          ""]

    # 4. maliyet
    L += ["## 4. Maliyet duyarlılığı (sinyal 24/96)", "",
          "| Varsayım | Toplam getiri | İşlem | Komisyon |", "|---|---|---|---|"]
    for r in a["costs"]:
        L.append(f"| {r.label} | {_pct(r.total_return)} | {r.trades} | "
                 f"{_share(r.fees / r.initial, 2)} |")
    L += ["", "Notlar: Al-tut masrafsızdır. Strateji ilk günlerde ısınma için bekler. "
          "Izgarada en iyi sonucu seçmek iyimser bir yanılgıdır; asıl ölçü 2 ve 3. bölümlerdir."]
    return "\n".join(L)


def summary_json(a: dict) -> dict:
    def r2d(r: Run):
        return {"ayar": r.label, "toplam_getiri": str(r.total_return),
                "en_buyuk_dusus": str(r.max_dd), "islem": r.trades, "komisyon": str(r.fees),
                "ort_yatirim_orani": str(r.exposure),
                "ceyrekler": {k: str(v) for k, v in r.period_returns.items()}}
    return {"donem": [a["start"].isoformat(), a["end"].isoformat()], "semboller": a["symbols"],
            "al_tut_ceyrekler": {k: str(v) for k, v in a["bh_periods"].items()},
            "izgara": [r2d(r) for r in a["grid"]], "izgara_sabit": [r2d(r) for r in a["grid_novol"]],
            "canli": r2d(a["live"]), "maliyet": [r2d(r) for r in a["costs"]]}


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="python -m jev.saglamlik",
                                description="Strateji sağlamlık testi (ızgara, çeyrekler, "
                                            "ileriye dönük seçim)")
    p.add_argument("--veri", required=True, type=Path,
                   help="SEMBOL-1h-YYYY-AA.csv kline dosyalarının klasörü")
    p.add_argument("--semboller", nargs="+", default=["BTCUSDT", "ETHUSDT"])
    p.add_argument("--rules", help="exchange_info.json (varsayılan: klasördeki ya da örnek)")
    p.add_argument("--out", type=Path, help="Raporu (.md) ve özeti (.json) buraya yaz")
    args = p.parse_args(argv)
    paths, syms = [], []
    for s in args.semboller:
        files = sorted(args.veri.glob(f"{s}-1h-*.csv"))
        if not files:
            p.exit(1, f"Hata: {args.veri} içinde {s}-1h-*.csv yok\n")
        paths += files
        syms += [s] * len(files)
    rules = args.rules or (str(args.veri / "exchange_info.json")
                           if (args.veri / "exchange_info.json").exists() else None)
    bars = [b for b in load_bars(paths, kline_symbols=syms)
            if all(s in b.prices for s in args.semboller)]
    a = analyse(bars, args.semboller, rules)
    text = report(a)
    print(text)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "saglamlik.md").write_text(text + "\n", encoding="utf-8")
        (args.out / "saglamlik.json").write_text(
            json.dumps(summary_json(a), indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
