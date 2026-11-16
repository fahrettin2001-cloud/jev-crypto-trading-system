"""Geniş tarama: trend kuralları çok sayıda coin ve ABD varlığında işe yarıyor mu?

Soru: "Yükseliş trendindeki her varlıktan küçük bir parça almak" yalnızca BTC+ETH
trendinden daha iyi mi? Üç evren ayrı ayrı test edilir:

- kripto: 2020 başında piyasa değeri en büyük, Binance'te USDT çifti olan 26 coin.
  Evren BUGÜN seçilmedi; sonradan çöken ya da borsadan çıkarılan coinler de içinde
  (hayatta kalma yanlılığını azaltmak için). Veri: data.binance.vision aylık arşivi
  (SHA-256 doğrulamalı; çıkarılmış coinlerin arşivi de durur).
- etf: 23 likit ABD ETF'i (endeks, sektör, tahvil, altın, emtia). Veri: Yahoo (yfinance).
- hisse: 2014 sonunda piyasa değeri en büyük 30 ABD şirketi (sonradan gerileyenler
  dahil). Veri: Yahoo (yfinance, temettü/bölünme düzeltmeli).

Her varlığa aynı 4 kural uygulanır (`jev.duygu.trend_weights`). Varyantlar:
- "eşit pay": etkin her varlığa 1/N pay × trend ağırlığı (her trenddekinden bir parça)
- "en iyi K": trenddekiler içinden son 90 günde en çok yükselen K varlık, 1/K pay
- "genişlik ≥ b": trenddeki varlık oranı b'nin altındaysa hiç yatırım yapma
Ayar YALNIZCA eğitim döneminde seçilir, test döneminde ölçülür. Karar kapanışta,
uygulama sonraki işlem gününde; her ağırlık değişiminde masraf düşülür.

Kullanım:
    python -m jev.genis_tarama indir-kripto --dir VERI --onbellek HAM
    python -m jev.genis_tarama indir-abd --dir VERI          # yfinance gerekir
    python -m jev.genis_tarama test --dir VERI --out rapor.md
Emir yok; yalnızca araştırma. Ücretli servis kullanılmaz.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from .binance_data import DownloadError, download_month, http_fetch
from .duygu import trend_weights

KRIPTO = ("BTC ETH XRP BCH LTC BNB EOS XTZ LINK XLM ADA TRX XMR ETC NEO DASH ATOM ZEC VET "
          "DOGE IOTA ONT QTUM BAT ALGO MATIC").split()
ETF = ("SPY QQQ IWM DIA EFA EEM VNQ TLT IEF LQD GLD SLV DBC USO XLK XLF XLE XLV XLI XLY "
       "XLP XLU XLB").split()
HISSE = ("AAPL GOOGL XOM MSFT BRK-B JNJ GE WFC AMZN META JPM PG WMT CVX VZ PFE T KO ORCL MRK "
         "DIS INTC IBM HD BAC CSCO C GILD V PEP").split()

EVRENLER = {
    # ad: (klasör, semboller, eğitim başı, eğitim sonu, masraf/ağırlık değişimi, yıllık gün)
    "kripto": ("kripto", [f"{c}USDT" for c in KRIPTO], date(2020, 1, 1), date(2023, 12, 31),
               0.001 + 0.0015, 365),
    "etf": ("etf", ETF, date(2008, 1, 1), date(2023, 12, 31), 0.0005, 252),
    "hisse": ("hisse", HISSE, date(2015, 6, 1), date(2023, 12, 31), 0.0005, 252),
}
WARMUP = 100
_ONE_DAY = timedelta(days=1)


# --- indirme ---------------------------------------------------------------------

def _write(path: Path, series: dict[date, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["gun", "kapanis"])
        for d, v in sorted(series.items()):
            w.writerow([d.isoformat(), repr(float(v))])


def _read(path: Path) -> dict[date, float]:
    with open(path, encoding="utf-8") as f:
        return {date.fromisoformat(r["gun"]): float(r["kapanis"]) for r in csv.DictReader(f)}


def download_crypto(out: Path, cache: Path, start="2019-06", end: str | None = None,
                    fetch=http_fetch, log=print) -> None:
    """Her sembolün günlük mumlarını aylık arşivden indirir, tek CSV'de birleştirir."""
    from .klines import load_binance_klines
    end = end or _last_full_month()
    for sym in EVRENLER["kripto"][1]:
        series, missing, errors = {}, 0, []
        for month in _months(start, end):
            try:
                path = download_month(sym, "1d", month, cache / sym, fetch=fetch)
            except (DownloadError, OSError, ValueError) as exc:
                if "404" in str(exc):
                    missing += 1      # listelenmeden önce ya da çıkarıldıktan sonra arşiv yok
                else:
                    errors.append(f"{month}: {exc}")
                continue
            for close_time, candle in load_binance_klines(path).items():
                series[(close_time - _ONE_DAY).date()] = float(candle.close)
        if series:
            _write(out / "kripto" / f"{sym}.csv", series)
            log(f"{sym}: {len(series)} gün ({min(series)} → {max(series)}), arşivi olmayan ay: {missing}"
                + (f", HATA {len(errors)}: {errors[0]}" if errors else ""))
        else:
            log(f"{sym}: veri yok" + (f" (HATA: {errors[0]})" if errors else ""))


def download_us(out: Path, start="2006-01-01", log=print) -> None:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise SystemExit("yfinance gerekli: /opt/jev/ajan-venv/bin/python ile çalıştırın") from exc
    for name in ("etf", "hisse"):
        syms = EVRENLER[name][1]
        data = yf.download(syms, start=start, auto_adjust=True, progress=False, threads=True)
        close = data["Close"]
        for s in syms:
            if s not in close:
                log(f"{s}: veri yok")
                continue
            col = close[s].dropna()
            series = {ts.date(): float(v) for ts, v in col.items() if v > 0}
            if series:
                _write(out / name / f"{s}.csv", series)
                log(f"{s}: {len(series)} gün ({min(series)} → {max(series)})")
            else:
                log(f"{s}: veri yok")


def _months(start: str, end: str) -> list[str]:
    """YYYY-AA aralığı (binance_data.months_between'deki 60 ay sınırı olmadan)."""
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    out = []
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _last_full_month() -> str:
    now = datetime.now(timezone.utc)
    y, m = (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)
    return f"{y:04d}-{m:02d}"




# --- test ------------------------------------------------------------------------

@dataclass(frozen=True)
class Variant:
    kind: str = "esit"          # esit | enIyiK | genislik
    k: int = 0
    breadth: float = 0.0

    def label(self) -> str:
        return {"esit": "Eşit pay (trenddeki her varlıktan bir parça)",
                "enIyiK": f"En iyi {self.k} (trenddekilerden 90g en güçlü)",
                "genislik": f"Eşit pay + genişlik ≥ %{self.breadth * 100:.0f}"}[self.kind]


GRID = [Variant()] + [Variant("enIyiK", k=k) for k in (3, 5, 8)] + \
       [Variant("genislik", breadth=b) for b in (0.3, 0.5, 0.7)]


@dataclass
class Result:
    label: str
    total: float
    cagr: float
    max_dd: float
    sharpe: float
    cost: float
    exposure: float
    holdings: float
    days: int
    returns: list[float]


class Universe:
    def __init__(self, prices: dict[str, dict[date, float]]):
        self.syms = sorted(prices)
        self.calendar = sorted(set().union(*(set(p) for p in prices.values())))
        idx = {d: i for i, d in enumerate(self.calendar)}
        n = len(self.calendar)
        self.close: dict[str, list[float | None]] = {}
        self.weight: dict[str, list[float]] = {}
        self.ready: dict[str, list[bool]] = {}
        for s in self.syms:
            series = prices[s]
            own_days = sorted(series)
            own_w = trend_weights([series[d] for d in own_days])
            c, w, r = [None] * n, [0.0] * n, [False] * n
            for j, d in enumerate(own_days):
                i = idx[d]
                c[i], w[i], r[i] = series[d], own_w[j], j + 1 >= WARMUP
            # tatil / eksik gün: son fiyat ve son ağırlık sürer (getiri 0)
            last_c, last_w, last_r = None, 0.0, False
            for i in range(n):
                if c[i] is None:
                    c[i], w[i], r[i] = last_c, last_w, last_r and last_c is not None
                last_c, last_w, last_r = c[i], w[i], r[i]
            self.close[s], self.weight[s], self.ready[s] = c, w, r
            # Son verisinden sonra (borsadan çıkarılan coin): etkin sayılmaz
            last_i = idx[own_days[-1]]
            for i in range(last_i + 1, n):
                self.ready[s][i] = False

    def momentum(self, s: str, i: int, look=90) -> float | None:
        c = self.close[s]
        if i < look or c[i] is None or c[i - look] is None:
            return None
        return c[i] / c[i - look] - 1

    def targets(self, i: int, v: Variant | None, buy_hold=False,
                only: tuple[str, ...] | None = None) -> dict[str, float]:
        active = [s for s in self.syms if self.ready[s][i] and (only is None or s in only)]
        if not active:
            return {}
        if buy_hold:
            return {s: 1 / len(active) for s in active}
        w = {s: self.weight[s][i] for s in active}
        if v is None or v.kind == "esit":
            return {s: w[s] / len(active) for s in active}
        if v.kind == "genislik":
            on = sum(1 for s in active if w[s] > 0) / len(active)
            return {s: (w[s] / len(active) if on >= v.breadth else 0.0) for s in active}
        cands = []
        for s in active:
            if w[s] > 0:
                m = self.momentum(s, i)
                cands.append((-9e9 if m is None else m, s))
        top = [s for _, s in sorted(cands, reverse=True)[: v.k]]
        return {s: w[s] / v.k for s in top}

    def simulate(self, v: Variant | None, start: date, end: date, cost: float, ann: int, *,
                 buy_hold=False, only: tuple[str, ...] | None = None, label="",
                 band: float = 0.1) -> Result:
        """Ağırlıklar fiyatla birlikte kayar (bedava günlük yeniden dengeleme yok).
        Strateji: bir varlığın kaymış ağırlığı hedeften payın `band` katından fazla
        saparsa ya da hedef 0 ise hedefe çekilir; masraf her gerçek değişimde düşülür.
        Al-tut: pencere başında etkin varlıklara eşit dağıtılır, sonra hiç dokunulmaz
        (borsadan çıkarılan varlık son fiyatından nakde döner)."""
        held: dict[str, float] = {}           # bar başındaki (kaymış) ağırlıklar
        eq, peak, mdd, rets, ctot, expo, hold = 1.0, 1.0, 0.0, [], 0.0, [], []
        cal = self.calendar
        started = False
        for i in range(len(cal) - 1):
            if not start <= cal[i + 1] <= end:
                continue
            if buy_hold:
                if not started:
                    new = self.targets(i, None, True, only)
                    started = bool(new)          # ilk etkin varlık olduğu gün alınır
                else:
                    new = {s: w for s, w in held.items() if self.ready[s][i]}
            else:
                tgt = self.targets(i, v, False, only)
                n_act = max(1, len(tgt))
                new = {}
                for s in set(tgt) | set(held):
                    t_, h_ = tgt.get(s, 0.0), held.get(s, 0.0)
                    sleeve = 1.0 / n_act if v is None or v.kind != "enIyiK" else 1.0 / v.k
                    new[s] = t_ if (t_ == 0.0 or abs(t_ - h_) > band * sleeve) else h_
                new = {s: w for s, w in new.items() if w > 0}
            c = sum(abs(new.get(s, 0.0) - held.get(s, 0.0)) for s in set(new) | set(held)) * cost
            r, grown = 0.0, {}
            for s, w in new.items():
                a, b = self.close[s][i], self.close[s][i + 1]
                g = (b / a - 1) if (a and b) else 0.0
                r += w * g
                grown[s] = w * (1 + g)
            net = r - c
            total = 1 + r
            held = {s: x / total for s, x in grown.items()} if total > 0 else {}
            eq *= 1 + net
            peak = max(peak, eq)
            mdd = min(mdd, eq / peak - 1)
            rets.append(net)
            ctot += c
            expo.append(sum(new.values()))
            hold.append(len(new))
        n = len(rets)
        if n < 2:
            return Result(label, 0, 0, 0, 0, 0, 0, 0, n, rets)
        sd = statistics.pstdev(rets)
        return Result(label or (v.label() if v else "Al-tut"), eq - 1, eq ** (ann / n) - 1, mdd,
                      statistics.fmean(rets) / sd * math.sqrt(ann) if sd > 0 else 0.0, ctot,
                      statistics.fmean(expo), statistics.fmean(hold), n, rets)


HEAD = ("| Strateji | Toplam | Yıllık | En büyük düşüş | Sharpe | Masraf | Ort. yatırım | Ort. varlık |\n"
        "|---|---|---|---|---|---|---|---|")


def _row(r: Result) -> str:
    return (f"| {r.label} | {r.total * 100:+.1f}% | {r.cagr * 100:+.1f}% | {r.max_dd * 100:.1f}% | "
            f"{r.sharpe:.2f} | %{r.cost * 100:.1f} | %{r.exposure * 100:.0f} | {r.holdings:.1f} |")


def load_universe(directory: Path, name: str) -> tuple[Universe, list[str]]:
    folder, syms = EVRENLER[name][0], EVRENLER[name][1]
    prices, notes = {}, []
    for s in syms:
        p = directory / folder / f"{s}.csv"
        if p.exists():
            series = _read(p)
            if len(series) > WARMUP:
                prices[s] = series
                continue
        notes.append(s)
    if not prices:
        raise ValueError(f"{name}: veri yok ({directory / folder})")
    return Universe(prices), notes


def universe_report(directory: Path, name: str) -> tuple[str, dict[str, list[float]], Universe]:
    u, missing = load_universe(directory, name)
    _, _, tr_start, tr_end, cost, ann = EVRENLER[name]
    last = u.calendar[-1]
    te_start = tr_end + _ONE_DAY
    train = [(u.simulate(v, tr_start, tr_end, cost, ann), v) for v in GRID]
    best_tr, best_v = max(train, key=lambda x: x[0].sharpe)
    te = lambda v, **kw: u.simulate(v, te_start, last, cost, ann, **kw)
    full = lambda v, **kw: u.simulate(v, tr_start, last, cost, ann, **kw)
    bh_te = te(None, buy_hold=True, label="Al-tut (evren, eşit başlangıç)")
    base_name, base_only = ({"kripto": ("BTC+ETH trend (mevcut strateji)", ("BTCUSDT", "ETHUSDT")),
                             "etf": ("Yalnızca SPY trend", ("SPY",)),
                             "hisse": ("", None)})[name]
    rows_te = [bh_te]
    if base_only and not all(s in u.syms for s in base_only):
        base_only = None
    if base_only:
        rows_te.append(te(None, only=base_only, label=base_name))
        bh_one = te(None, buy_hold=True, only=base_only[:1],
                    label=f"Al-tut ({base_only[0].replace('USDT', '')})")
        rows_te.insert(1, bh_one)
    grid_te = [te(v) for v in GRID]
    chosen_te = next(r for r, v in zip(grid_te, GRID) if v == best_v)
    rows_te += grid_te
    lines = [f"## {name.upper()} — {len(u.syms)} varlık", "",
             f"Eğitim {tr_start} → {tr_end}, test {te_start} → {last}. Masraf her ağırlık değişiminde "
             f"%{cost * 100:.2f}. Eksik/yetersiz veri: {', '.join(missing) or 'yok'}.", "",
             f"**Eğitimde seçilen:** {best_v.label()} (eğitim Sharpe {best_tr.sharpe:.2f}). "
             f"**Testte:** Sharpe {chosen_te.sharpe:.2f}, toplam {chosen_te.total * 100:+.1f}%, "
             f"en büyük düşüş {chosen_te.max_dd * 100:.1f}%.", "",
             "### Test dönemi (eğitimde kullanılmadı)", "", HEAD] + [_row(r) for r in rows_te]
    lines += ["", "### Eğitim dönemi", "", HEAD, _row(u.simulate(None, tr_start, tr_end, cost, ann,
                                                                   buy_hold=True, label="Al-tut (evren, eşit başlangıç)"))]
    if base_only:
        lines.append(_row(u.simulate(None, tr_start, tr_end, cost, ann, only=base_only, label=base_name)))
    lines += [_row(r) for r, _ in train]
    lines += ["", "### Tüm dönem (bilgi)", "", HEAD, _row(full(None, buy_hold=True, label="Al-tut (evren, eşit başlangıç)")),
              _row(full(best_v)), ""]
    series = {"secilen": u.simulate(best_v, te_start, last, cost, ann).returns}
    return "\n".join(lines), series, u


def mixed_report(directory: Path) -> str:
    """Kripto (eşit pay) + ETF (eşit pay), %50/%50, test döneminde (2024→). Kripto
    takvimine göre; ETF getirisi hafta sonu 0. İki yarı arasında günlük yeniden
    dengeleme masrafsız varsayılır (yaklaşık; iki yarının kendi masrafları dahil)."""
    try:
        uk, _ = load_universe(directory, "kripto")
        ue, _ = load_universe(directory, "etf")
    except ValueError as exc:
        return f"## KARIŞIK\n\nAtlandı: {exc}\n"
    start = date(2024, 1, 1)
    end = min(uk.calendar[-1], ue.calendar[-1])

    def daily(u, name):
        _, _, _, _, cost, _ = EVRENLER[name]
        res = u.simulate(Variant(), start, end, cost, 365)
        days = [d for d in u.calendar if start <= d <= end][: len(res.returns)]
        return dict(zip(days, res.returns))

    rk, re_ = daily(uk, "kripto"), daily(ue, "etf")
    days = sorted(rk)
    if len(days) < 2:
        return "## KARIŞIK\n\nAtlandı: 2024 sonrası veri yok\n"

    def stats(rs):
        eq, pk, mdd = 1.0, 1.0, 0.0
        for x in rs:
            eq *= 1 + x
            pk = max(pk, eq)
            mdd = min(mdd, eq / pk - 1)
        sd = statistics.pstdev(rs)
        return eq - 1, mdd, (statistics.fmean(rs) / sd * math.sqrt(365) if sd else 0)

    out = ["## KARIŞIK — kripto eşit pay %50 + ETF eşit pay %50 (test dönemi)", "",
           "| Portföy | Toplam | En büyük düşüş | Sharpe (365 gün) |", "|---|---|---|---|"]
    for lab, rs in (("Yalnızca kripto", [rk[d] for d in days]),
                    ("Yalnızca ETF", [re_.get(d, 0.0) for d in days]),
                    ("%50 / %50", [0.5 * rk[d] + 0.5 * re_.get(d, 0.0) for d in days])):
        t, m, s = stats(rs)
        out.append(f"| {lab} | {t * 100:+.1f}% | {m * 100:.1f}% | {s:.2f} |")
    return "\n".join(out) + "\n"


def full_report(directory: Path, names=("kripto", "etf", "hisse")) -> str:
    parts = ["# Geniş tarama — trend kuralları çok sayıda varlıkta", "",
             "Aynı 4 trend kuralı her varlığa uygulanır. Kripto evreni 2020 başının en büyük coinlerinden, hisse "
             "evreni 2014 sonunun en büyük şirketlerinden seçildi (sonradan çökenler dahil); yine de seçim "
             "tamamen yanlılıksız değildir. Karar kapanışta, uygulama sonraki işlem gününde; masraflar dahil. "
             "Geçmiş sonuç gelecekteki getiriyi göstermez.", ""]
    for n in names:
        try:
            text, _, _ = universe_report(directory, n)
        except ValueError as exc:
            text = f"## {n.upper()}\n\nAtlandı: {exc}\n"
        parts.append(text)
    if "kripto" in names and "etf" in names:
        try:
            parts.append(mixed_report(directory))
        except (ValueError, statistics.StatisticsError) as exc:
            parts.append(f"## KARIŞIK\n\nAtlandı: {exc}\n")
    parts.append("Veri: Binance (data.binance.vision), Yahoo Finance (yfinance).")
    return "\n".join(parts) + "\n"


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="python -m jev.genis_tarama", description="Geniş evren trend testi (ücretsiz veri)")
    sub = p.add_subparsers(dest="komut", required=True)
    a = sub.add_parser("indir-kripto")
    a.add_argument("--dir", type=Path, required=True)
    a.add_argument("--onbellek", type=Path, required=True, help="Aylık ham arşiv klasörü")
    a.add_argument("--start", default="2019-06")
    b = sub.add_parser("indir-abd")
    b.add_argument("--dir", type=Path, required=True)
    t = sub.add_parser("test")
    t.add_argument("--dir", type=Path, required=True)
    t.add_argument("--out", type=Path)
    t.add_argument("--evren", nargs="+", default=["kripto", "etf", "hisse"], choices=list(EVRENLER))
    args = p.parse_args(argv)
    if args.komut == "indir-kripto":
        download_crypto(args.dir, args.onbellek, args.start)
    elif args.komut == "indir-abd":
        download_us(args.dir)
    else:
        rep = full_report(args.dir, tuple(args.evren))
        if args.out:
            args.out.write_text(rep, encoding="utf-8")
        print(rep)


if __name__ == "__main__":
    main()
