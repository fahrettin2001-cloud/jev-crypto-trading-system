"""Karar günlüğü ve güven kalibrasyonu.

Her strateji / model kararı (AL, SAT, BEKLE) güven puanı ve o andaki fiyatla
kaydedilir. Sonra belirli bir süre (`horizon` bar) sonraki fiyata bakılarak
kararın haklı çıkıp çıkmadığı ölçülür:

- AL   haklı: getiri >  eşik  (fiyat maliyetten fazla yükseldi)
- SAT  haklı: getiri < -eşik  (fiyat maliyetten fazla düştü)
- BEKLE haklı: |getiri| <= eşik (anlamlı hareket olmadı)

Eşik varsayılan olarak bir al-sat turunun maliyetidir (2 × komisyon + 2 × kayma).
Bu ölçüm, işlemin gerçekleşip gerçekleşmediğinden bağımsızdır: reddedilen bir
kararın da isabeti ölçülür. Kalibrasyon, güven aralıklarına göre "söylenen
güven" ile "gerçekleşen isabet"i karşılaştırır.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Sequence

from .fees import D

BUY, SELL, HOLD = "BUY", "SELL", "HOLD"
ACTIONS = (BUY, SELL, HOLD)
DEFAULT_BINS = tuple(Decimal(x) / 10 for x in range(0, 11))  # 0.0, 0.1, ..., 1.0


@dataclass(frozen=True)
class Decision:
    timestamp: datetime
    symbol: str
    action: str
    price: Decimal                    # karar anındaki kapanış
    confidence: Decimal | None = None  # 0..1; yoksa kalibrasyona girmez
    source: str = ""                  # ör. "sma-kesisim(...)" ya da "jev-1.13.0"
    reason: str = ""
    status: str = ""                  # "gerçekleşti", "reddedildi: ...", "bekle"

    def __post_init__(self) -> None:
        if self.action not in ACTIONS:
            raise ValueError(f"Karar BUY, SELL ya da HOLD olmalı: {self.action}")
        if self.timestamp.utcoffset() is None:
            raise ValueError("Karar zamanı saat dilimi içermeli")
        price = D(self.price)
        if not price.is_finite() or price <= 0:
            raise ValueError("Karar fiyatı pozitif olmalı")
        object.__setattr__(self, "price", price)
        if self.confidence is not None:
            c = D(self.confidence)
            if not c.is_finite() or not 0 <= c <= 1:
                raise ValueError("Güven 0 ile 1 arasında olmalı")
            object.__setattr__(self, "confidence", c)

    def to_json(self) -> str:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        d["price"] = str(self.price)
        d["confidence"] = None if self.confidence is None else str(self.confidence)
        return json.dumps(d, ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str) -> "Decision":
        d = json.loads(line)
        d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        return cls(**d)


class DecisionJournal:
    """Bellekte karar listesi; isteğe bağlı olarak JSONL dosyasına ekler (append-only)."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else None
        self.decisions: list[Decision] = []

    def record(self, decision: Decision) -> Decision:
        self.decisions.append(decision)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(decision.to_json() + "\n")
        return decision

    @classmethod
    def load(cls, path: str | Path) -> "DecisionJournal":
        j = cls()
        with open(path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if line.strip():
                    try:
                        j.decisions.append(Decision.from_json(line))
                    except (ValueError, KeyError, TypeError) as exc:
                        raise ValueError(f"{path}:{n}: okunamayan karar satırı") from exc
        return j


# --- sonuç değerlendirme --------------------------------------------------------


@dataclass(frozen=True)
class Outcome:
    decision: Decision
    future_price: Decimal | None
    ret: Decimal | None        # future / price - 1
    correct: bool | None       # None: ufuk verinin dışında


def evaluate(decisions: Iterable[Decision], closes: dict[str, Sequence[tuple[datetime, Decimal]]],
             horizon: int, threshold) -> list[Outcome]:
    """`closes`: sembol → zaman sıralı (zaman, kapanış). Karar zamanındaki bardan
    `horizon` bar sonraki kapanışa bakılır."""
    if not isinstance(horizon, int) or horizon < 1:
        raise ValueError("horizon pozitif tam sayı olmalı")
    tau = D(threshold)
    if not tau.is_finite() or tau < 0:
        raise ValueError("Eşik negatif olamaz")
    index = {s: [t for t, _ in series] for s, series in closes.items()}
    out = []
    for d in decisions:
        series = closes.get(d.symbol)
        times = index.get(d.symbol)
        future = ret = correct = None
        if series:
            i = bisect.bisect_left(times, d.timestamp)
            if i < len(times) and times[i] == d.timestamp and i + horizon < len(series):
                future = D(series[i + horizon][1])
                ret = future / d.price - 1
                correct = (ret > tau if d.action == BUY
                           else ret < -tau if d.action == SELL
                           else abs(ret) <= tau)
        out.append(Outcome(d, future, ret, correct))
    return out


@dataclass(frozen=True)
class CalibrationRow:
    low: Decimal
    high: Decimal
    count: int
    mean_confidence: Decimal | None
    hit_rate: Decimal | None
    enough_data: bool

    @property
    def gap(self) -> Decimal | None:
        if self.hit_rate is None or self.mean_confidence is None:
            return None
        return self.hit_rate - self.mean_confidence


@dataclass
class CalibrationReport:
    rows: list[CalibrationRow]
    evaluated: int                 # sonucu ölçülebilen karar
    unresolved: int                # ufuk verinin dışında kalan
    without_confidence: int        # güven puanı olmayan (kalibrasyona girmeyen)
    hit_rate: Decimal | None       # tüm ölçülen kararlar
    brier: Decimal | None          # ortalama (güven - sonuç)^2; düşük daha iyi, 0.25 = yazı tura
    by_action: dict[str, tuple[int, Decimal | None]] = field(default_factory=dict)
    min_count: int = 20


def calibration(outcomes: Sequence[Outcome], bins: Sequence[Decimal] = DEFAULT_BINS,
                min_count: int = 20) -> CalibrationReport:
    bins = [D(b) for b in bins]
    if len(bins) < 2 or any(a >= b for a, b in zip(bins, bins[1:])) or bins[0] < 0 or bins[-1] > 1:
        raise ValueError("Aralık sınırları 0..1 içinde ve artan olmalı")
    resolved = [o for o in outcomes if o.correct is not None]
    scored = [o for o in resolved if o.decision.confidence is not None]
    rows = []
    for k, (lo, hi) in enumerate(zip(bins, bins[1:])):
        last = k == len(bins) - 2
        group = [o for o in scored
                 if lo <= o.decision.confidence < hi or (last and o.decision.confidence == hi)]
        n = len(group)
        mean_c = sum((o.decision.confidence for o in group), Decimal(0)) / n if n else None
        hits = Decimal(sum(o.correct for o in group)) / n if n else None
        rows.append(CalibrationRow(lo, hi, n, mean_c, hits, n >= min_count))
    by_action = {}
    for a in ACTIONS:
        g = [o for o in resolved if o.decision.action == a]
        by_action[a] = (len(g), Decimal(sum(o.correct for o in g)) / len(g) if g else None)
    brier = (sum(((o.decision.confidence - (1 if o.correct else 0)) ** 2 for o in scored),
                 Decimal(0)) / len(scored)) if scored else None
    return CalibrationReport(
        rows=rows, evaluated=len(resolved), unresolved=len(outcomes) - len(resolved),
        without_confidence=sum(1 for o in resolved if o.decision.confidence is None),
        hit_rate=Decimal(sum(o.correct for o in resolved)) / len(resolved) if resolved else None,
        brier=brier, by_action=by_action, min_count=min_count)


def format_calibration(rep: CalibrationReport, horizon: int, threshold) -> str:
    pct = lambda x: "—" if x is None else f"%{x * 100:.1f}"
    names = {BUY: "AL", SELL: "SAT", HOLD: "BEKLE"}
    lines = [
        f"Karar isabeti ({horizon} bar sonrası, eşik %{D(threshold) * 100:.2f})",
        f"Ölçülen karar      : {rep.evaluated} (veri bittiği için ölçülemeyen {rep.unresolved})",
        f"Genel isabet       : {pct(rep.hit_rate)}",
        "Karar türüne göre  : " + ", ".join(
            f"{names[a]} {n} karar / {pct(h)}" for a, (n, h) in rep.by_action.items() if n),
    ]
    scored = sum(r.count for r in rep.rows)
    if not scored:
        lines.append("Güven puanı olan karar yok; kalibrasyon tablosu çıkarılamadı.")
        return "\n".join(lines)
    lines += [
        f"Brier puanı        : {rep.brier:.4f} (0 mükemmel, 0.25 yazı-tura düzeyi; düşük daha iyi)",
        "",
        "Güven aralığı | Karar | Ort. güven | Gerçek isabet | Fark    | Not",
        "--------------|-------|------------|---------------|---------|-----",
    ]
    for r in rep.rows:
        if r.count == 0:
            continue
        gap = r.gap
        note = ("az veri" if not r.enough_data
                else "fazla iddialı" if gap < Decimal("-0.05")
                else "fazla çekingen" if gap > Decimal("0.05") else "uyumlu")
        span = f"%{r.low * 100:.0f}–%{r.high * 100:.0f}"
        lines.append(f"{span:<14}| {r.count:>5} | "
                     f"{pct(r.mean_confidence):>10} | {pct(r.hit_rate):>13} | "
                     f"{'—' if gap is None else f'{gap * 100:+.1f}':>7} | {note}")
    if rep.without_confidence:
        lines.append(f"Güven puanı olmayan {rep.without_confidence} karar tabloya girmedi.")
    lines.append(f"Not: {rep.min_count} karardan az olan aralıklar güvenilir değildir.")
    return "\n".join(lines)


def write_outcomes_csv(outcomes: Sequence[Outcome], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["zaman", "sembol", "karar", "guven", "fiyat", "sonraki_fiyat", "getiri",
                    "hakli", "kaynak", "durum", "gerekce"])
        for o in outcomes:
            d = o.decision
            w.writerow([d.timestamp.isoformat(), d.symbol, d.action,
                        "" if d.confidence is None else d.confidence, d.price,
                        "" if o.future_price is None else o.future_price,
                        "" if o.ret is None else o.ret,
                        "" if o.correct is None else int(o.correct), d.source, d.status, d.reason])
    return path


def closes_from_bars(bars) -> dict[str, list[tuple[datetime, Decimal]]]:
    out: dict[str, list[tuple[datetime, Decimal]]] = {}
    for b in bars:
        for s, p in b.prices.items():
            out.setdefault(s, []).append((b.timestamp, p))
    return out


def main(argv=None) -> None:
    """Kayıtlı bir karar günlüğünü (JSONL) fiyat verisiyle değerlendirir."""
    from .klines import load_bars
    parser = argparse.ArgumentParser(prog="python -m jev.journal",
                                     description="Karar günlüğü isabet ve güven kalibrasyonu")
    parser.add_argument("--journal", required=True, type=Path, help="JSONL karar günlüğü")
    parser.add_argument("--prices", nargs="+", required=True)
    parser.add_argument("--kline-symbols", nargs="+")
    parser.add_argument("--horizon", type=int, default=24)
    parser.add_argument("--threshold", default="0.003", help="Haklı sayılma eşiği (0.003 = %%0,3)")
    parser.add_argument("--min-count", type=int, default=20)
    parser.add_argument("--out", type=Path, help="Karar sonuçları CSV")
    args = parser.parse_args(argv)
    try:
        journal = DecisionJournal.load(args.journal)
        bars = load_bars(args.prices, kline_symbols=args.kline_symbols)
        outcomes = evaluate(journal.decisions, closes_from_bars(bars), args.horizon, args.threshold)
        rep = calibration(outcomes, min_count=args.min_count)
        if args.out:
            write_outcomes_csv(outcomes, args.out)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Hata: {exc}\n")
    print(format_calibration(rep, args.horizon, args.threshold))


if __name__ == "__main__":
    main()
