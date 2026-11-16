"""Ajan kurulu: TradingAgents çok ajanlı analizini GÖLGE modda çalıştırır.

TradingAgents (https://github.com/TauricResearch/TradingAgents, Apache-2.0) her coin
için analist (piyasa, sosyal/duygu, haber), boğa/ayı araştırmacı, trader, risk ekibi
ve portföy yöneticisi ajanlarını çalıştırır; sonunda 5 kademeli bir not verir
(Buy / Overweight / Hold / Underweight / Sell).

Bu modül o notu bizim karar günlüğü biçimine (`jev.journal.Decision`) çevirir ve
ayrı bir klasöre yazar. **Hiçbir emir vermez, sanal portföye de dokunmaz**: canlı
sanal bot (`jev.live`) ve bağımsız risk katmanı değişmez. Amaç, ajanların
kararlarını haftalarca kaydedip isabetlerini ölçmek; işe yararsa ileride filtre
olarak eklemek.

Klasör (varsayılan /var/lib/jev/ajan):
    ajan_kararlar.jsonl   karar günlüğü (JSONL, yalnızca eklenir)
    raporlar/<tarih>-<SEMBOL>.md   ajanların tam raporları
    ozet.md               son kararlar + bugüne kadarki isabet
    gunluk.log            çalışma özeti ve hatalar

Kullanım:
    python -m jev.ajan_kurulu calistir --dir /var/lib/jev/ajan --symbols BTCUSDT ETHUSDT
    python -m jev.ajan_kurulu ozet --dir /var/lib/jev/ajan

Analiz tarihi varsayılan olarak DÜNdür (UTC): yalnızca kapanmış günlük mum ve o
güne kadar yayınlanmış veri kullanılır.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable

from .journal import BUY, HOLD, SELL, DecisionJournal, Decision, evaluate
from .live import LiveError, fetch_closed_candles, http_fetch

DEFAULT_DIR = Path("/var/lib/jev/ajan")
SOURCE_PREFIX = "tradingagents"
DAY = timedelta(days=1)
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{5,20}$")

# 5 kademeli not → bizim karar eylemi. Ara kademeler aynı yönde sayılır.
RATING_TO_ACTION = {
    "buy": BUY, "overweight": BUY,
    "hold": HOLD,
    "underweight": SELL, "sell": SELL,
}

# Raporda saklanan TradingAgents durum alanları (sırayla).
REPORT_FIELDS = (
    ("market_report", "Piyasa (teknik) analisti"),
    ("sentiment_report", "Duygu analisti"),
    ("news_report", "Haber analisti"),
    ("fundamentals_report", "Temel analist"),
    ("investment_plan", "Araştırma yöneticisi (boğa/ayı tartışması sonucu)"),
    ("trader_investment_plan", "Trader önerisi"),
    ("final_trade_decision", "Portföy yöneticisi — son karar"),
)

# Ölçüm: karar gününün kapanışından `HORIZON` gün sonraki kapanış.
HORIZON_DAYS = 5
THRESHOLD = Decimal("0.01")   # BUY için +%1'den fazla, SELL için −%1'den fazla hareket


class AjanError(RuntimeError):
    pass


# Runner: (sembol, analiz_tarihi "YYYY-AA-GG") → (TradingAgents son durumu, not)
Runner = Callable[[str, str], tuple[dict, str]]


def tradingagents_runner(config_overrides: dict | None = None,
                         analysts: Iterable[str] = ("market", "social", "news")) -> Runner:
    """Gerçek TradingAgents çalıştırıcısı. Paket yalnızca burada içe aktarılır; ana
    proje ve testler TradingAgents kurulu olmadan çalışır."""
    try:
        from tradingagents.default_config import build_default_config
        from tradingagents.graph.trading_graph import TradingAgentsGraph
    except ImportError as exc:
        raise AjanError("TradingAgents kurulu değil. Kurulum: docs/AJAN-KURULU.md "
                        "(deploy/install-ajan.sh)") from exc
    config = build_default_config()   # TRADINGAGENTS_* ortam değişkenlerini okur
    config.update(config_overrides or {})
    graph = TradingAgentsGraph(selected_analysts=tuple(analysts), debug=False, config=config)

    def run(symbol: str, trade_date: str) -> tuple[dict, str]:
        state, signal = graph.propagate(symbol, trade_date, asset_type="crypto")
        return dict(state or {}), str(signal)
    run.model = f"{config.get('llm_provider')}:{config.get('deep_think_llm')}/{config.get('quick_think_llm')}"
    return run


def rating_to_action(signal: str) -> tuple[str, str]:
    """(eylem, durum). Okunamayan not (REVIEW vb.) işlem sayılmaz: HOLD + 'inceleme'."""
    key = (signal or "").strip().lower()
    if key in RATING_TO_ACTION:
        return RATING_TO_ACTION[key], ""
    return HOLD, f"inceleme: okunamayan not {signal!r}"


@contextmanager
def _locked(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / ".kilit", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise AjanError("Başka bir ajan çalışması sürüyor (kilit alınamadı)") from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _log(directory: Path, message: str, now: datetime) -> None:
    with open(directory / "gunluk.log", "a", encoding="utf-8") as f:
        f.write(f"{now.isoformat(timespec='seconds')} {message}\n")


def daily_close(symbol: str, day: date, fetch=http_fetch, now: datetime | None = None) -> tuple[datetime, Decimal]:
    """`day` gününün (UTC) kapanmış günlük mumu: (kapanış zamanı, kapanış fiyatı)."""
    now = now or datetime.now(timezone.utc)
    candles = fetch_closed_candles(symbol, "1d", 10, now, fetch=fetch)
    close_time = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + DAY
    if close_time not in candles:
        raise AjanError(f"{symbol} için {day} günlük mumu yok ya da henüz kapanmadı")
    return close_time, candles[close_time].close


def _already_done(journal_path: Path) -> set[tuple[str, str]]:
    if not journal_path.exists():
        return set()
    return {(d.symbol, d.timestamp.isoformat()) for d in DecisionJournal.load(journal_path).decisions}


def _write_report(directory: Path, symbol: str, day: date, signal: str, action: str,
                  state: dict, model: str, seconds: float) -> Path:
    out = directory / "raporlar" / f"{day.isoformat()}-{symbol}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    parts = [f"# Ajan kurulu — {symbol} — {day.isoformat()}", "",
             f"- Son not: **{signal}** → kayıt: {action} (gölge mod, emir yok)",
             f"- Model: {model}", f"- Süre: {seconds:.0f} sn", ""]
    for key, title in REPORT_FIELDS:
        text = state.get(key)
        if isinstance(text, str) and text.strip():
            parts += [f"## {title}", "", text.strip(), ""]
    out.write_text("\n".join(parts), encoding="utf-8")
    return out


def run_day(directory: Path, symbols: Iterable[str], day: date, runner: Runner, *,
            fetch=http_fetch, clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
            ) -> list[str]:
    """Her sembol için ajanları bir kez çalıştırır. Bir sembolün hatası diğerlerini
    durdurmaz. Aynı gün+sembol ikinci kez çalıştırılmaz (maliyet koruması)."""
    symbols = list(symbols)
    for s in symbols:
        if not _SYMBOL_RE.match(s):
            raise ValueError(f"Geçersiz sembol: {s}")
    if day >= clock().date():
        raise AjanError("Analiz günü kapanmış bir gün olmalı (en geç dün, UTC)")
    model = getattr(runner, "model", "bilinmiyor")
    messages = []
    with _locked(directory):
        journal = DecisionJournal(directory / "ajan_kararlar.jsonl")
        done = _already_done(journal.path)
        for symbol in symbols:
            now = clock()
            try:
                ts, price = daily_close(symbol, day, fetch=fetch, now=now)
                if (symbol, ts.isoformat()) in done:
                    messages.append(f"{symbol} {day}: zaten kayıtlı, atlandı")
                    continue
                t0 = time.monotonic()
                state, signal = runner(symbol, day.isoformat())
                seconds = time.monotonic() - t0
                action, status = rating_to_action(signal)
                report = _write_report(directory, symbol, day, signal, action, state, model, seconds)
                journal.record(Decision(timestamp=ts, symbol=symbol, action=action, price=price,
                                        confidence=None, source=f"{SOURCE_PREFIX}:{model}",
                                        reason=f"not={signal}; rapor={report.name}",
                                        status=status or "gölge"))
                messages.append(f"{symbol} {day}: {signal} → {action} ({seconds:.0f} sn)")
            except Exception as exc:  # noqa: BLE001 — bir sembolün hatası diğerini durdurmasın
                messages.append(f"{symbol} {day}: HATA {type(exc).__name__}: {exc}")
        for m in messages:
            _log(directory, m, clock())
        write_summary(directory, fetch=fetch, clock=clock)
    return messages


@dataclass
class SymbolStats:
    total: int = 0
    measured: int = 0
    correct: int = 0


def summary_text(directory: Path, fetch=http_fetch,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> str:
    path = directory / "ajan_kararlar.jsonl"
    if not path.exists():
        return "# Ajan kurulu özeti\n\nHenüz karar yok.\n"
    decisions = DecisionJournal.load(path).decisions
    now = clock()
    closes: dict[str, list[tuple[datetime, Decimal]]] = {}
    price_note = ""
    for s in sorted({d.symbol for d in decisions}):
        try:
            closes[s] = sorted(fetch_closed_candles(s, "1d", 1000, now, fetch=fetch)
                               .items())
            closes[s] = [(t, c.close) for t, c in closes[s]]
        except (LiveError, ValueError) as exc:
            price_note = f"\n> Fiyat alınamadı, isabet eksik olabilir: {exc}\n"
    outcomes = evaluate(decisions, closes, HORIZON_DAYS, THRESHOLD)
    stats: dict[str, SymbolStats] = {}
    by_action: dict[str, SymbolStats] = {}
    for o in outcomes:
        for key, table in ((o.decision.symbol, stats), (o.decision.action, by_action)):
            st = table.setdefault(key, SymbolStats())
            st.total += 1
            if o.correct is not None:
                st.measured += 1
                st.correct += int(o.correct)

    def pct(st: SymbolStats) -> str:
        return f"%{100 * st.correct / st.measured:.0f} ({st.correct}/{st.measured})" if st.measured else "—"

    lines = ["# Ajan kurulu özeti (gölge mod — emir yok)", "",
             f"Güncelleme: {now.isoformat(timespec='minutes')} · Toplam karar: {len(decisions)} · "
             f"Ölçüm: {HORIZON_DAYS} gün sonraki kapanış, eşik ±%{THRESHOLD * 100:.0f}", price_note,
             "## İsabet", "", "| Kırılım | Karar | İsabet |", "|---|---|---|"]
    for key, st in sorted(stats.items()):
        lines.append(f"| {key} | {st.total} | {pct(st)} |")
    for key, st in sorted(by_action.items()):
        lines.append(f"| {key} | {st.total} | {pct(st)} |")
    lines += ["", "En az 20 ölçülmüş karar olmadan isabet oranına güvenmeyin.", "",
              "## Son kararlar", "", "| Gün | Sembol | Not | Kayıt | Fiyat | "
              f"{HORIZON_DAYS}g getiri | Haklı mı |", "|---|---|---|---|---|---|---|"]
    for o in sorted(outcomes, key=lambda o: o.decision.timestamp, reverse=True)[:20]:
        d = o.decision
        note = d.reason.split(";")[0].removeprefix("not=")
        ret = "bekliyor" if o.ret is None else f"{o.ret * 100:+.1f}%"
        ok = "—" if o.correct is None else ("evet" if o.correct else "hayır")
        lines.append(f"| {(d.timestamp - DAY).date()} | {d.symbol} | {note} | {d.action} | "
                     f"{d.price:.2f} | {ret} | {ok} |")
    return "\n".join(lines) + "\n"


def write_summary(directory: Path, **kw) -> Path:
    out = directory / "ozet.md"
    out.write_text(summary_text(directory, **kw), encoding="utf-8")
    return out


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m jev.ajan_kurulu",
                                     description="TradingAgents ajan kurulu — gölge mod, emir yok")
    sub = parser.add_subparsers(dest="komut", required=True)
    run = sub.add_parser("calistir", help="Ajanları bir gün için çalıştır")
    run.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    run.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"])
    run.add_argument("--date", help="Analiz günü YYYY-AA-GG (varsayılan: dün, UTC)")
    run.add_argument("--analysts", nargs="+", default=["market", "social", "news"],
                     help="TradingAgents analistleri (kripto için temel analiz genelde boş)")
    run.add_argument("--language", default="Turkish", help="Rapor dili")
    summ = sub.add_parser("ozet", help="Özet raporu yeniden yaz ve göster")
    summ.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args(argv)
    try:
        if args.komut == "ozet":
            print(write_summary(args.dir).read_text(encoding="utf-8"))
            return
        day = (date.fromisoformat(args.date) if args.date
               else datetime.now(timezone.utc).date() - DAY)
        runner = tradingagents_runner({"output_language": args.language}, analysts=args.analysts)
        for m in run_day(args.dir, args.symbols, day, runner):
            print(m)
    except (AjanError, LiveError, ValueError, OSError) as exc:
        parser.exit(1, f"Hata: {exc}\n")


if __name__ == "__main__":
    main()
