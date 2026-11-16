"""Duygu endeksi: bedava, model çağrısı yapmayan piyasa duygusu ölçümü.

Kaynaklar (hepsi anahtarsız):
- Korku ve Açgözlülük Endeksi (alternative.me, 2018-02'den beri günlük, 0-100).
  Kaynak gösterilmesi şartıyla ticari kullanım serbesttir: "Veri: alternative.me".
- Binance USDⓈ-M vadeli fonlama oranı (8 saatte bir; kalabalığın kaldıraçlı
  alım/satım iştahı). BTCUSDT 2019-09'dan beri.
- Binance küresel long/short hesap oranı (yalnızca son 30 gün verilir; bu yüzden
  her gün kaydedilir).

Kullanım:
    python -m jev.duygu indir --dir /var/lib/jev/duygu          # geçmiş veriyi indir
    python -m jev.duygu test  --dir /var/lib/jev/duygu          # geçmiş testi raporu
    python -m jev.duygu gunluk --dir /var/lib/jev/duygu         # bugünkü endeksi kaydet

Geçmiş testi: yavaş trend topluluğu (4 kural) tek başına ve duygu filtreleriyle
karşılaştırılır. Ayarlar YALNIZCA eğitim döneminde (2018-02 → 2023-12) seçilir,
sonra hiç dokunulmamış test döneminde (2024-01 → bugün) ölçülür. Karar gün
kapanışında verilir, ertesi gün uygulanır; komisyon + kayma her ağırlık
değişiminde düşülür. Emir yok; yalnızca ölçüm ve kayıt.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Sequence

from .live import LiveError, http_fetch

FNG_URL = "https://api.alternative.me/fng/?limit=0&format=json"
FUNDING_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
LONGSHORT_URL = "https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
KLINES_URL = "https://data-api.binance.vision/api/v3/klines"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
DAY = timedelta(days=1)
COST = 0.001 + 0.0005            # komisyon %0,1 + kayma 5 bps
TRAIN_END = date(2023, 12, 31)
START = date(2018, 2, 1)         # Korku/Açgözlülük verisinin başlangıcı

Fetch = Callable[[str], bytes]


def _utc_day(ms_or_s: int) -> date:
    ts = ms_or_s / 1000 if ms_or_s > 10**11 else ms_or_s
    return datetime.fromtimestamp(ts, timezone.utc).date()


def _ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


def _json(fetch: Fetch, url: str):
    try:
        return json.loads(fetch(url))
    except ValueError as exc:
        raise LiveError(f"JSON değil: {url.split('?')[0]}") from exc


# --- indirme ---------------------------------------------------------------------

def fetch_fear_greed(fetch: Fetch = http_fetch) -> dict[date, int]:
    data = _json(fetch, FNG_URL)
    rows = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise LiveError("Korku/Açgözlülük verisi boş")
    out = {}
    for r in rows:
        v = int(r["value"])
        if not 0 <= v <= 100:
            raise LiveError(f"Geçersiz endeks değeri: {v}")
        out[_utc_day(int(r["timestamp"]))] = v
    return dict(sorted(out.items()))


def fetch_daily_closes(symbol: str, start: date, end: date, fetch: Fetch = http_fetch) -> dict[date, float]:
    """Kapanmış günlük mumlar: {gün: kapanış}. 1000'lik sayfalarla."""
    out, cursor = {}, start
    while cursor <= end:
        rows = _json(fetch, f"{KLINES_URL}?symbol={symbol}&interval=1d&startTime={_ms(cursor)}&limit=1000")
        if not rows:
            break
        for r in rows:
            d = _utc_day(int(r[0]))
            if d <= end:
                out[d] = float(r[4])
        last = _utc_day(int(rows[-1][0]))
        if last < cursor:
            break
        cursor = last + DAY
        if len(rows) < 1000:
            break
    return out


def fetch_funding_daily(symbol: str, start: date, end: date, fetch: Fetch = http_fetch) -> dict[date, float]:
    """Günlük toplam fonlama oranı (genelde 3 ödeme). {gün: toplam oran}."""
    sums: dict[date, float] = {}
    cursor = _ms(start)
    stop = _ms(end + DAY)
    while cursor < stop:
        rows = _json(fetch, f"{FUNDING_URL}?symbol={symbol}&startTime={cursor}&limit=1000")
        if not rows:
            break
        for r in rows:
            t = int(r["fundingTime"])
            if t >= stop:
                continue
            d = _utc_day(t)
            sums[d] = sums.get(d, 0.0) + float(r["fundingRate"])
        nxt = int(rows[-1]["fundingTime"]) + 1
        if nxt <= cursor or len(rows) < 1000:
            break
        cursor = nxt
    return dict(sorted(sums.items()))


def fetch_long_short(symbol: str, fetch: Fetch = http_fetch) -> dict[date, float]:
    rows = _json(fetch, f"{LONGSHORT_URL}?symbol={symbol}&period=1d&limit=30")
    return {_utc_day(int(r["timestamp"])): float(r["longShortRatio"]) for r in rows}


def _write_series(path: Path, header: str, series: dict[date, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["gun", header])
        for d, v in sorted(series.items()):
            w.writerow([d.isoformat(), v])


def _read_series(path: Path) -> dict[date, float]:
    with open(path, encoding="utf-8") as f:
        return {date.fromisoformat(r["gun"]): float(list(r.values())[1]) for r in csv.DictReader(f)}


def download(directory: Path, fetch: Fetch = http_fetch, today: date | None = None) -> list[str]:
    today = today or datetime.now(timezone.utc).date()
    end = today - DAY                                   # yalnızca kapanmış günler
    msgs = []
    fng = {d: v for d, v in fetch_fear_greed(fetch).items() if d <= end}
    _write_series(directory / "korku_acgozluluk.csv", "deger", fng)
    msgs.append(f"Korku/Açgözlülük: {len(fng)} gün ({min(fng)} → {max(fng)})")
    for s in SYMBOLS:
        closes = fetch_daily_closes(s, START - timedelta(days=150), end, fetch)
        _write_series(directory / f"kapanis_{s}.csv", "kapanis", closes)
        msgs.append(f"{s} kapanış: {len(closes)} gün")
        try:
            fund = fetch_funding_daily(s, START, end, fetch)
            _write_series(directory / f"fonlama_{s}.csv", "gunluk_oran", fund)
            msgs.append(f"{s} fonlama: {len(fund)} gün")
        except LiveError as exc:
            msgs.append(f"{s} fonlama ALINAMADI ({exc}); test fonlama filtresiz yapılır")
    return msgs


# --- sinyaller -------------------------------------------------------------------

def _prefix(xs: Sequence[float]) -> list[float]:
    out = [0.0]
    for x in xs:
        out.append(out[-1] + x)
    return out


def _sma(pre: list[float], n: int, i: int) -> float | None:
    return (pre[i + 1] - pre[i + 1 - n]) / n if i + 1 >= n else None


def trend_weights(closes: Sequence[float]) -> list[float]:
    """Yavaş trend topluluğu: 4 kuralın ortalaması (0, .25, .5, .75, 1).
    Kurallar: SMA10>SMA40, SMA20>SMA100 (±%1 bant), fiyat>SMA50, fiyat>SMA100 (±%2 bant).
    i günündeki ağırlık yalnızca i ve öncesini kullanır."""
    states = [0.0, 0.0, 0.0, 0.0]
    out = []
    pre = _prefix(closes)
    for i, p in enumerate(closes):
        s10, s40, s20, s100, s50 = (_sma(pre, n, i) for n in (10, 40, 20, 100, 50))
        if s40 is not None:
            states[0] = 1.0 if s10 > s40 else 0.0
        if s100 is not None:
            if s20 > s100 * 1.01:
                states[1] = 1.0
            elif s20 < s100 * 0.99:
                states[1] = 0.0
            if p > s100 * 1.02:
                states[3] = 1.0
            elif p < s100 * 0.98:
                states[3] = 0.0
        if s50 is not None:
            states[2] = 1.0 if p > s50 else 0.0
        out.append(sum(states) / 4 if s100 is not None else 0.0)
    return out


@dataclass(frozen=True)
class Filter:
    """Duygu filtresi. greed: endeks bu değer ve üstündeyse ağırlık yarıya iner.
    fear: endeks bu değer ve altındaysa ağırlık en az `fear_floor` olur (ters yönlü alım).
    funding: 7 günlük ortalama fonlama yıllık bu oranın üstündeyse ağırlık yarıya iner."""
    greed: int | None = None
    fear: int | None = None
    fear_floor: float = 0.5
    funding: float | None = None

    def label(self) -> str:
        parts = []
        if self.greed is not None:
            parts.append(f"açgözlülük≥{self.greed}→yarım")
        if self.fear is not None:
            parts.append(f"korku≤{self.fear}→en az %{self.fear_floor * 100:.0f}")
        if self.funding is not None:
            parts.append(f"fonlama>%{self.funding * 100:.0f}/yıl→yarım")
        return ", ".join(parts) or "filtresiz"


def funding_annual_7d(funding: dict[date, float], d: date) -> float | None:
    vals = [funding[d - k * DAY] for k in range(7) if d - k * DAY in funding]
    return (sum(vals) / len(vals)) * 365 if len(vals) >= 5 else None


def apply_filter(w: float, f: Filter, fng: float | None, fund_ann: float | None) -> float:
    if f.greed is not None and fng is not None and fng >= f.greed:
        w *= 0.5
    if f.funding is not None and fund_ann is not None and fund_ann > f.funding:
        w *= 0.5
    if f.fear is not None and fng is not None and fng <= f.fear:
        w = max(w, f.fear_floor)
    return w


# --- simülasyon -----------------------------------------------------------------

@dataclass
class Result:
    label: str
    total: float
    cagr: float
    max_dd: float
    sharpe: float
    cost: float
    exposure: float
    days: int


def simulate(days: list[date], closes: dict[str, list[float]], fng: dict[date, float],
             funding: dict[str, dict[date, float]], f: Filter | None, *,
             start: date, end: date, buy_hold: bool = False) -> Result:
    """Eşit ağırlıklı BTC/ETH. Ağırlık i. gün kapanışında hesaplanır, i+1. günün
    getirisine uygulanır (geleceği görmeme)."""
    syms = list(closes)
    trend = _trend_cache(closes)
    prev = {s: 0.0 for s in syms}
    eq, peak, max_dd, rets, cost_total, expo = 1.0, 1.0, 0.0, [], 0.0, []
    for i in range(len(days) - 1):
        d = days[i]
        if not start <= days[i + 1] <= end:
            continue
        r, c, e = 0.0, 0.0, 0.0
        for s in syms:
            if buy_hold:
                w = 1.0
            else:
                w = trend[s][i]
                if f is not None:
                    w = apply_filter(w, f, fng.get(d), funding_annual_7d(funding.get(s, {}), d))
            w /= len(syms)
            c += abs(w - prev[s]) * COST
            prev[s] = w
            r += w * (closes[s][i + 1] / closes[s][i] - 1)
            e += w
        net = r - c
        eq *= 1 + net
        peak = max(peak, eq)
        max_dd = min(max_dd, eq / peak - 1)
        rets.append(net)
        cost_total += c
        expo.append(e)
    n = len(rets)
    if n < 2:
        return Result(_label(f, buy_hold), 0, 0, 0, 0, 0, 0, n)
    sd = statistics.pstdev(rets)
    return Result(_label(f, buy_hold), eq - 1, eq ** (365 / n) - 1, max_dd,
                  (statistics.fmean(rets) / sd * math.sqrt(365)) if sd > 0 else 0.0,
                  cost_total, statistics.fmean(expo), n)


_TREND: dict[tuple, dict[str, list[float]]] = {}


def _trend_cache(closes: dict[str, list[float]]) -> dict[str, list[float]]:
    key = tuple((s, len(v), v[0] if v else 0, v[-1] if v else 0) for s, v in closes.items())
    if key not in _TREND:
        _TREND.clear()
        _TREND[key] = {s: trend_weights(v) for s, v in closes.items()}
    return _TREND[key]


def _label(f: Filter | None, buy_hold: bool) -> str:
    return "Al-tut (BTC+ETH eşit)" if buy_hold else ("Trend topluluğu" if f is None else f"Trend + {f.label()}")


def grid() -> list[Filter]:
    out = []
    for g in (70, 75, 80, 85):
        out.append(Filter(greed=g))
    for fe in (10, 15, 20, 25):
        out.append(Filter(fear=fe))
    for h in (0.2, 0.3, 0.5):
        out.append(Filter(funding=h))
    for g in (75, 80):
        for fe in (15, 20):
            out.append(Filter(greed=g, fear=fe))
            out.append(Filter(greed=g, fear=fe, funding=0.3))
    return out


def load(directory: Path):
    fng = _read_series(directory / "korku_acgozluluk.csv")
    raw = {s: _read_series(directory / f"kapanis_{s}.csv") for s in SYMBOLS}
    days = sorted(set.intersection(*(set(v) for v in raw.values())))
    closes = {s: [raw[s][d] for d in days] for s in SYMBOLS}
    funding = {}
    for s in SYMBOLS:
        p = directory / f"fonlama_{s}.csv"
        funding[s] = _read_series(p) if p.exists() else {}
    return days, closes, fng, funding


def _row(r: Result) -> str:
    return (f"| {r.label} | {r.total * 100:+.1f}% | {r.cagr * 100:+.1f}% | {r.max_dd * 100:.1f}% | "
            f"{r.sharpe:.2f} | %{r.cost * 100:.1f} | %{r.exposure * 100:.0f} |")


HEAD = ("| Strateji | Toplam | Yıllık | En büyük düşüş | Sharpe | Masraf | Ort. yatırım |\n"
        "|---|---|---|---|---|---|---|")


def backtest_report(directory: Path) -> str:
    days, closes, fng, funding = load(directory)
    last = days[-1]
    train = (START, TRAIN_END)
    test = (TRAIN_END + DAY, last)
    base_tr = simulate(days, closes, fng, funding, None, start=train[0], end=train[1])
    cands = [(simulate(days, closes, fng, funding, f, start=train[0], end=train[1]), f) for f in grid()]
    cands.sort(key=lambda x: x[0].sharpe, reverse=True)
    best_tr, best_f = cands[0]
    # Test dönemi: eğitimde seçilen tek ayar + bütün ızgara (komşuluk kontrolü için)
    res = lambda f, bh=False: simulate(days, closes, fng, funding, f, start=test[0], end=test[1], buy_hold=bh)
    bh_te, base_te, best_te = res(None, True), res(None), res(best_f)
    grid_te = [res(f) for f in grid()]
    beat = sum(r.sharpe > base_te.sharpe for r in grid_te)
    full = lambda f, bh=False: simulate(days, closes, fng, funding, f, start=START, end=last, buy_hold=bh)

    fund_start = {s: (min(funding[s]).isoformat() if funding[s] else "yok") for s in SYMBOLS}
    verdict = ("Duygu filtresi test döneminde trendi **iyileştirdi** (Sharpe "
               f"{base_te.sharpe:.2f} → {best_te.sharpe:.2f})." if best_te.sharpe > base_te.sharpe + 0.05 else
               "Duygu filtresi test döneminde trendi **anlamlı biçimde iyileştirmedi** (Sharpe "
               f"{base_te.sharpe:.2f} → {best_te.sharpe:.2f}).")
    lines = [
        "# Duygu filtresi geçmiş testi", "",
        f"Veri: Binance günlük kapanış BTCUSDT+ETHUSDT, Korku/Açgözlülük (alternative.me), Binance fonlama "
        f"(başlangıç: {fund_start}). Eğitim {train[0]} → {train[1]}, test {test[0]} → {test[1]}. "
        f"Masraf her ağırlık değişiminde %{COST * 100:.2f}; karar kapanışta, uygulama ertesi gün.", "",
        f"**Eğitimde seçilen filtre:** {best_f.label()} (eğitim Sharpe {best_tr.sharpe:.2f}, filtresiz trend "
        f"{base_tr.sharpe:.2f}).", "",
        f"**Sonuç:** {verdict} Izgaradaki {len(grid_te)} filtrenin {beat}'i test döneminde filtresiz trendi "
        "Sharpe'ta geçti; bu sayı düşükse seçilen filtrenin başarısı tesadüf olabilir.", "",
        "## Test dönemi (eğitimde hiç kullanılmadı)", "", HEAD, _row(bh_te), _row(base_te), _row(best_te), "",
        "## Tüm dönem (bilgi amaçlı; ayar seçimi eğitimde yapıldı)", "", HEAD,
        _row(full(None, True)), _row(full(None)), _row(full(best_f)), "",
        "## Izgara — eğitim ve test Sharpe", "", "| Filtre | Eğitim | Test |", "|---|---|---|",
        f"| filtresiz | {base_tr.sharpe:.2f} | {base_te.sharpe:.2f} |",
    ]
    tr_map = {c[1]: c[0] for c in cands}
    for f, r in zip(grid(), grid_te):
        lines.append(f"| {f.label()} | {tr_map[f].sharpe:.2f} | {r.sharpe:.2f} |")
    lines += ["", "Veri: alternative.me Korku ve Açgözlülük Endeksi; Binance. "
              "Geçmiş sonuç gelecekteki getiriyi göstermez."]
    return "\n".join(lines) + "\n"


# --- günlük kayıt ----------------------------------------------------------------

def fng_label(v: int) -> str:
    return ("aşırı korku" if v <= 24 else "korku" if v <= 44 else "nötr" if v <= 55
            else "açgözlülük" if v <= 75 else "aşırı açgözlülük")


def daily(directory: Path, fetch: Fetch = http_fetch, today: date | None = None) -> dict:
    """Dünün (UTC) duygu değerlerini `duygu_kayit.jsonl`'a ekler ve özet yazar."""
    today = today or datetime.now(timezone.utc).date()
    d = today - DAY
    rec: dict = {"gun": d.isoformat()}
    fng = fetch_fear_greed(fetch)
    if d in fng:
        rec["korku_acgozluluk"] = fng[d]
        rec["etiket"] = fng_label(fng[d])
    for s in SYMBOLS:
        try:
            fund = fetch_funding_daily(s, d - 6 * DAY, d, fetch)
            ann = funding_annual_7d(fund, d)
            rec[f"fonlama_yillik_7g_{s}"] = None if ann is None else round(ann, 4)
        except LiveError as exc:
            rec[f"fonlama_yillik_7g_{s}"] = None
            rec.setdefault("hatalar", []).append(f"{s} fonlama: {exc}")
        try:
            ls = fetch_long_short(s, fetch)
            rec[f"long_short_{s}"] = ls.get(d)
        except LiveError as exc:
            rec[f"long_short_{s}"] = None
            rec.setdefault("hatalar", []).append(f"{s} long/short: {exc}")
    path = directory / "duygu_kayit.jsonl"
    directory.mkdir(parents=True, exist_ok=True)
    done = set()
    if path.exists():
        done = {json.loads(x)["gun"] for x in path.read_text(encoding="utf-8").splitlines() if x.strip()}
    if rec["gun"] not in done:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    (directory / "duygu_ozet.md").write_text(summary(path), encoding="utf-8")
    return rec


def summary(path: Path) -> str:
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    lines = ["# Duygu endeksi (bedava, model çağrısı yok)", "",
             "| Gün | Korku/Açgözlülük | BTC fonlama (yıllık, 7g) | ETH fonlama | BTC long/short | ETH long/short |",
             "|---|---|---|---|---|---|"]
    pct = lambda v: "—" if v is None else f"%{v * 100:.1f}"
    num = lambda v: "—" if v is None else f"{v:.2f}"
    for r in rows[-14:][::-1]:
        fg = r.get("korku_acgozluluk")
        lines.append(f"| {r['gun']} | {'—' if fg is None else str(fg) + ' (' + r.get('etiket', '') + ')'} | "
                     f"{pct(r.get('fonlama_yillik_7g_BTCUSDT'))} | {pct(r.get('fonlama_yillik_7g_ETHUSDT'))} | "
                     f"{num(r.get('long_short_BTCUSDT'))} | {num(r.get('long_short_ETHUSDT'))} |")
    lines += ["", "Veri: alternative.me Korku ve Açgözlülük Endeksi; Binance vadeli işlem verisi."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="python -m jev.duygu", description="Bedava duygu endeksi ve geçmiş testi")
    sub = p.add_subparsers(dest="komut", required=True)
    for name, hlp in (("indir", "Geçmiş veriyi indir"), ("test", "Geçmiş testi raporu"),
                      ("gunluk", "Dünün duygu değerlerini kaydet")):
        sp = sub.add_parser(name, help=hlp)
        sp.add_argument("--dir", type=Path, default=Path("/var/lib/jev/duygu"))
        if name == "test":
            sp.add_argument("--out", type=Path, help="Raporu dosyaya da yaz")
    a = p.parse_args(argv)
    try:
        if a.komut == "indir":
            for m in download(a.dir):
                print(m)
        elif a.komut == "test":
            rep = backtest_report(a.dir)
            if a.out:
                a.out.write_text(rep, encoding="utf-8")
            print(rep)
        else:
            print(json.dumps(daily(a.dir), ensure_ascii=False, indent=1))
    except (LiveError, ValueError, OSError, KeyError) as exc:
        p.exit(1, f"Hata: {exc}\n")


if __name__ == "__main__":
    main()
