"""Canlı sanal işlem: gerçek zamanlı Binance fiyatlarıyla, sahte parayla.

Gerçek emir göndermez, hesap veya API anahtarı kullanmaz. Yalnızca Binance
Global'in halka açık mum verisini (data-api.binance.vision) okur.

Çalışma biçimi: sunucu (systemd zamanlayıcısı ya da cron) `run` komutunu her
mum kapanışından kısa süre sonra bir kez çalıştırır. Komut:

1. Durum klasörünü kilitler (aynı anda iki çalışma olmaz).
2. Kayıtlı simülatörü (`durum.pkl`) yükler.
3. `DURDUR` dosyası varsa hiçbir şey yapmadan çıkar (acil durdurma).
4. Son kapanan mumları indirir; daha önce işlenmemiş her bar için backtest ile
   AYNI motoru (`Simulator.step`) çalıştırır. `max_lag`'den eski barlar işlem
   için kullanılmaz, yalnızca stratejiye gösterilir (eski veriyle işlem yok).
5. Yeni işlemleri, sonuçlanan kararları ve varlık değerini dosyalara ekler,
   durumu atomik olarak kaydeder.

Durum klasörü: durum.pkl, ayarlar.json, kararlar.jsonl, islemler.csv,
varlik_egrisi.csv, redler.csv, gunluk.log, DURDUR (isteğe bağlı).
İsteğe bağlı Jev gölge modu (`jev_golge.json` varsa): işlem kaydedildikten sonra
olasılık tahminini `golge.jsonl`'a yazar, kararları değiştirmez (bkz. `jev.jev_golge`).
`durum.pkl` yalnızca bu programın kendi yazdığı dosyadır; başka kaynaktan
gelen pkl dosyası yüklenmemelidir.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import json
import os
import pickle
import re
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable

from .backtest import BacktestConfig, Simulator, format_report
from .exchange_rules import ExchangeRules
from .fees import D, FeeSchedule
from . import jev_golge
from .journal import (DecisionJournal, calibration, evaluate, format_calibration)
from .klines import Candle, bars_from_series
from .risk import RiskLimits
from .sizing import VolatilityTargetSizer
from .strategy import BuyAndHold, Combined, SmaCross

KLINES_URL = "https://data-api.binance.vision/api/v3/klines"
INTERVALS = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{5,20}$")
STATE, SETTINGS, STOP = "durum.pkl", "ayarlar.json", "DURDUR"
MAX_RESPONSE = 2 * 1024 * 1024

Fetch = Callable[[str], bytes]
Clock = Callable[[], datetime]


class LiveError(RuntimeError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise LiveError("Beklenmeyen yönlendirme")


def http_fetch(url: str, timeout: float = 20) -> bytes:
    opener = urllib.request.build_opener(_NoRedirect())
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "jev-crypto-trading-system/0.1"})
    try:
        with opener.open(req, timeout=timeout) as resp:
            data = resp.read(MAX_RESPONSE + 1)
    except urllib.error.HTTPError as exc:
        raise LiveError(f"HTTP {exc.code}: {url}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise LiveError(f"Bağlantı hatası: {exc}") from exc
    if len(data) > MAX_RESPONSE:
        raise LiveError("Cevap boyut sınırını aştı")
    return data


def fetch_closed_candles(symbol: str, interval: str, limit: int, now: datetime,
                         fetch: Fetch = http_fetch) -> dict[datetime, Candle]:
    """Son `limit` mumdan KAPANMIŞ olanları {kapanış zamanı: Candle} döndürür."""
    if not _SYMBOL_RE.match(symbol):
        raise ValueError(f"Geçersiz sembol: {symbol}")
    if interval not in INTERVALS:
        raise ValueError(f"Geçersiz aralık: {interval}")
    if not 1 <= limit <= 1000:
        raise ValueError("limit 1..1000 olmalı")
    try:
        rows = json.loads(fetch(f"{KLINES_URL}?symbol={symbol}&interval={interval}&limit={limit}"))
    except ValueError as exc:
        raise LiveError("Mum verisi JSON değil") from exc
    if not isinstance(rows, list):
        raise LiveError("Mum verisi liste değil")
    out: dict[datetime, Candle] = {}
    step = timedelta(minutes=INTERVALS[interval])
    for row in rows:
        try:
            open_ms, close_ms = int(row[0]), int(row[6])
            o, h, l, c = (Decimal(str(x)) for x in row[1:5])
            qv = Decimal(str(row[7]))
        except (TypeError, ValueError, IndexError, ArithmeticError) as exc:
            raise LiveError(f"Bozuk mum satırı: {row!r}") from exc
        if any(not v.is_finite() or v <= 0 for v in (o, h, l, c)) or not (l <= min(o, c)
                                                                          and max(o, c) <= h):
            raise LiveError(f"Geçersiz fiyatlar: {row!r}")
        close_time = datetime.fromtimestamp((close_ms + 1) / 1000, timezone.utc)
        open_time = datetime.fromtimestamp(open_ms / 1000, timezone.utc)
        if close_time - open_time != step:
            raise LiveError(f"Mum süresi beklenenle uyuşmuyor: {row!r}")
        if close_time <= now:  # henüz kapanmamış mumu alma
            out[close_time] = Candle(o, h, l, c, qv if qv.is_finite() and qv >= 0 else None)
    return out


# --- durum ---------------------------------------------------------------------


@dataclass
class LiveState:
    settings: dict
    sim: Simulator
    written_trades: int = 0
    written_rejections: int = 0
    written_decisions: set = field(default_factory=set)   # issued listesindeki indeksler
    created_at: datetime = field(default_factory=_utcnow)
    skipped_stale: int = 0


@contextmanager
def _locked(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / ".kilit", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise LiveError("Başka bir çalışma sürüyor (kilit alınamadı)") from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _save(directory: Path, state: LiveState) -> None:
    tmp = directory / (STATE + ".tmp")
    with open(tmp, "wb") as f:
        pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, directory / STATE)


class _StateUnpickler(pickle.Unpickler):
    """`python -m jev.live` ile yazılmış eski durum dosyalarında sınıf `__main__.LiveState`
    olarak kayıtlıdır; bunu her zaman `jev.live.LiveState`'e yönlendirir."""

    def find_class(self, module, name):
        if module == "__main__" and name == "LiveState":
            return LiveState
        return super().find_class(module, name)


def _load(directory: Path) -> LiveState:
    path = directory / STATE
    if not path.exists():
        raise LiveError(f"{path} yok; önce `init` çalıştırın")
    with open(path, "rb") as f:
        state = _StateUnpickler(f).load()  # yalnızca bu programın yazdığı dosya
    if not isinstance(state, LiveState):
        raise LiveError("Durum dosyası tanınmadı")
    return state


def _log(directory: Path, message: str, now: datetime) -> None:
    line = f"{now.isoformat(timespec='seconds')} {message}"
    print(line)
    with open(directory / "gunluk.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _append_csv(path: Path, header: list[str], rows: list[list]) -> None:
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        if new:
            w.writerow(header)
        w.writerows(rows)


# --- strateji ve ayarlar ---------------------------------------------------------


def build_strategy(settings: dict):
    parts = []
    for symbol in settings["symbols"]:
        if settings["strategy"] == "al-tut":
            parts.append(BuyAndHold(symbol, Decimal(settings["fraction"]) / len(settings["symbols"])))
            continue
        sizer = None
        if settings.get("vol_target"):
            sizer = VolatilityTargetSizer(settings["vol_target"], settings["vol_window"],
                                          24 * 60 // INTERVALS[settings["interval"]],
                                          max_fraction=settings["fraction"])
        parts.append(SmaCross(symbol, settings["fast"], settings["slow"], settings["fraction"],
                              stop_loss_pct=settings.get("stop_loss_pct"),
                              take_profit_pct=settings.get("take_profit_pct"), sizer=sizer,
                              max_quote=settings.get("max_trade_notional")))
    return parts[0] if len(parts) == 1 else Combined(parts)


def build_config(settings: dict) -> BacktestConfig:
    risk_fields = {k: settings[k] for k in ("max_trade_notional", "max_position_notional",
                                           "min_cash_reserve") if settings.get(k)}
    risk = RiskLimits(allowed_symbols=settings["symbols"], **risk_fields)
    return BacktestConfig(
        initial_cash=D(settings["cash"]),
        fees=FeeSchedule(taker_rate=settings["taker_rate"], maker_rate=settings["taker_rate"]),
        slippage_bps=D(settings["slippage_bps"]),
        rules=ExchangeRules.load(settings["rules"]) if settings.get("rules") else None,
        risk=risk,
        max_volume_share=D(settings["max_volume_share"]) if settings.get("max_volume_share") else None,
    )


def warmup_bars_needed(settings: dict) -> int:
    if settings["strategy"] == "al-tut":
        return 0
    return max(settings["slow"] + 1,
               (settings.get("vol_window") or 0) + 1 if settings.get("vol_target") else 0)


# --- komutlar --------------------------------------------------------------------


def init(directory: Path, settings: dict, *, fetch: Fetch = http_fetch, clock: Clock = _utcnow
         ) -> LiveState:
    directory = Path(directory)
    if (directory / STATE).exists():
        raise LiveError(f"{directory} zaten başlatılmış; yeniden başlatmak için klasörü değiştirin")
    for s in settings["symbols"]:
        if not _SYMBOL_RE.match(s):
            raise ValueError(f"Geçersiz sembol: {s}")
    if settings["interval"] not in INTERVALS:
        raise ValueError(f"Geçersiz aralık: {settings['interval']}")
    config = build_config(settings)          # ayarları erken doğrula
    sim = Simulator(build_strategy(settings), config)
    now = clock()
    with _locked(directory):
        need = warmup_bars_needed(settings)
        if need:
            if need + 1 > 1000:
                raise ValueError("Isınma için 1000'den fazla mum gerekiyor")
            series = {s: fetch_closed_candles(s, settings["interval"], need + 1, now, fetch)
                      for s in settings["symbols"]}
            for bar in bars_from_series(series):
                sim.observe(bar)              # ısınma: işlem yok
        state = LiveState(settings=settings, sim=sim, created_at=now)
        (directory / SETTINGS).write_text(json.dumps(settings, indent=2, ensure_ascii=False),
                                          encoding="utf-8")
        _save(directory, state)
        _log(directory, f"başlatıldı: {sim.source}; ısınma {len(sim.equity_curve)} bar; "
                        f"son bar {sim.last_timestamp}", now)
    return state


def run_once(directory: Path, *, fetch: Fetch = http_fetch, clock: Clock = _utcnow,
             catchup: int = 48, shadow_predictor: jev_golge.Predictor | None = None) -> dict:
    """Yeni kapanan barları işler. Döndürür: özet sözlük."""
    directory = Path(directory)
    with _locked(directory):
        now = clock()
        if (directory / STOP).exists():
            _log(directory, "DURDUR dosyası var; hiçbir işlem yapılmadı", now)
            return {"durduruldu": True, "islenen": 0}
        state = _load(directory)
        sim, st = state.sim, state.settings
        step = timedelta(minutes=INTERVALS[st["interval"]])
        max_lag = step * st.get("max_lag_bars", 2)
        series = {s: fetch_closed_candles(s, st["interval"], min(catchup + 1, 1000), now, fetch)
                  for s in st["symbols"]}
        new_bars = [b for b in bars_from_series(series)
                    if sim.last_timestamp is None or b.timestamp > sim.last_timestamp]
        if sim.last_timestamp and new_bars and new_bars[0].timestamp - sim.last_timestamp > step:
            _log(directory, f"UYARI: {sim.last_timestamp} sonrasında veri boşluğu var "
                            f"(ilk yeni bar {new_bars[0].timestamp})", now)
        traded = stale = 0
        for bar in new_bars:
            if now - bar.timestamp > max_lag:
                sim.observe(bar)
                stale += 1
            else:
                sim.step(bar)
                traded += 1
        state.skipped_stale += stale

        trades = sim.portfolio.trades[state.written_trades:]
        notes = sim.e.notes[state.written_trades:]
        _append_csv(directory / "islemler.csv",
                    ["zaman", "sembol", "yon", "tur", "miktar", "fiyat", "komisyon",
                     "gerceklesen_kz", "gerekce"],
                    [[t.timestamp.isoformat(), t.symbol, t.side, n.kind, t.quantity, t.price,
                      t.fee, t.realized_pnl, n.reason] for t, n in zip(trades, notes)])
        state.written_trades += len(trades)
        rejections = sim.e.rejections[state.written_rejections:]
        _append_csv(directory / "redler.csv", ["zaman", "sembol", "yon", "tur", "neden"],
                    [[r.timestamp.isoformat(), r.intent.symbol, r.intent.side, r.kind, r.reason]
                     for r in rejections])
        state.written_rejections += len(rejections)
        processed = sim.equity_curve[-len(new_bars):] if new_bars else []
        _append_csv(directory / "varlik_egrisi.csv", ["zaman", "toplam_varlik"],
                    [[ts.isoformat(), v] for ts, v in processed])
        journal = DecisionJournal(directory / "kararlar.jsonl")
        decisions = sim.decisions()
        newly = [i for i, d in enumerate(decisions)
                 if i not in state.written_decisions and d.status != "bekliyor"]
        for i in newly:
            journal.record(decisions[i])
            state.written_decisions.add(i)
        _save(directory, state)
        equity = sim.equity_curve[-1][1] if sim.equity_curve else sim.portfolio.cash
        summary = {"durduruldu": False, "islenen": traded, "eski_atlanan": stale,
                   "yeni_islem": len(trades), "yeni_red": len(rejections),
                   "son_bar": sim.last_timestamp.isoformat() if sim.last_timestamp else None,
                   "varlik": str(equity.quantize(Decimal("0.01")))}
        _log(directory, "çalıştı: " + json.dumps(summary, ensure_ascii=False), now)
        if not new_bars:
            last = sim.last_timestamp
            if last is not None and now - last > max_lag + step:
                _log(directory, f"UYARI: yeni kapanmış mum gelmedi; son bar {last}", now)
        # İşlem durumu yukarıda kaydedildi; gölge mod ondan sonra ve yalıtılmış çalışır.
        _run_shadow(directory, state, now, step, max_lag, shadow_predictor)
        return summary


def _run_shadow(directory: Path, state: LiveState, now: datetime, step: timedelta,
                max_lag: timedelta, predictor) -> None:
    """Jev gölge modu. Hiçbir hatası dışarı taşmaz; işlem durumuna dokunmaz."""
    try:
        cfg = jev_golge.ShadowSettings.load(directory)
        if not cfg.etkin:
            return
        if predictor is None:
            predictor = jev_golge.typesafe_predictor(cfg.model)
        n = jev_golge.record_predictions(
            directory, state.sim.closes, state.settings["symbols"], step, now, cfg, predictor,
            max_lag, log=lambda m: _log(directory, m, now))
        if n:
            _log(directory, f"Jev gölge: {n} tahmin kaydedildi (işlemler etkilenmedi)", now)
    except jev_golge.ShadowError as exc:
        _log(directory, f"Jev gölge: atlandı ({exc})", now)
    except Exception as exc:  # noqa: BLE001 - gölge mod botu asla durdurmaz
        _log(directory, f"Jev gölge: atlandı ({type(exc).__name__})", now)


def shadow_report(directory: Path, csv_path: Path | None = None) -> str:
    directory = Path(directory)
    state = _load(directory)
    outcomes = jev_golge.resolve(jev_golge.read_log(directory), state.sim.closes)
    if csv_path is not None:
        Path(csv_path).unlink(missing_ok=True)
        _append_csv(Path(csv_path), jev_golge.RESULT_HEADER, jev_golge.outcome_rows(outcomes))
    cfg = jev_golge.ShadowSettings.load(directory)
    head = (f"Ayar: {'AÇIK' if cfg.etkin else 'kapalı'}; ufuk {cfg.ufuk_bar} bar, "
            f"her {cfg.her_n_bar} barda bir, günde en çok {cfg.gunluk_cagri_siniri} çağrı")
    return head + "\n" + jev_golge.report(outcomes)


def status(directory: Path, horizon: int = 24) -> str:
    directory = Path(directory)
    state = _load(directory)
    sim = state.sim
    lines = [f"Klasör             : {directory}",
             f"Başlatma           : {state.created_at.isoformat(timespec='seconds')}",
             f"Son işlenen bar    : {sim.last_timestamp}",
             f"Acil durdurma      : {'AÇIK (DURDUR dosyası var)' if (directory / STOP).exists() else 'kapalı'}",
             f"Eski veri yüzünden işlemsiz geçen bar: {state.skipped_stale}",
             f"Açık pozisyonlar   : " + (", ".join(f"{s} {p.quantity}" for s, p in
                                                     sim.portfolio.positions.items()) or "yok"),
             f"Nakit              : {sim.portfolio.cash:.2f} {sim.config.quote}", ""]
    if sim.equity_curve:
        lines.append(format_report(sim.result()))
        decisions = [d for d in sim.decisions() if d.status != "bekliyor"]
        if decisions:
            cfg = sim.config
            threshold = 2 * cfg.fees.taker_rate + 2 * cfg.slippage_bps / 10000
            outcomes = evaluate(decisions, sim.closes, horizon, threshold)
            lines += ["", format_calibration(calibration(outcomes), horizon, threshold)]
    return "\n".join(lines)


def shadow_try(directory: Path, predictor=None) -> str:
    """Tek bir Jev çağrısıyla bağlantıyı dener (kayıt yazmaz, işlem yapmaz)."""
    directory = Path(directory)
    state = _load(directory)
    cfg = jev_golge.ShadowSettings.load(directory)
    symbol = (cfg.semboller or state.settings["symbols"])[0]
    history = state.sim.closes[symbol][-cfg.gecmis_bar:]
    step = timedelta(minutes=INTERVALS[state.settings["interval"]])
    predictor = predictor or jev_golge.typesafe_predictor(cfg.model)
    p = jev_golge.parse_probability(jev_golge.call_with_timeout(
        lambda: predictor(symbol, history, cfg.ufuk_bar, step), cfg.zaman_asimi_sn))
    ts, price = history[-1]
    return (f"Jev cevap verdi: {symbol} kapanışı {ts + cfg.ufuk_bar * step:%Y-%m-%d %H:%M} UTC'de "
            f"{price} üstünde olma olasılığı {p} (kayıt yazılmadı, işlem yok)")


def check(fetch: Fetch = http_fetch, clock: Clock = _utcnow) -> str:
    now = clock()
    candles = fetch_closed_candles("BTCUSDT", "1h", 3, now, fetch)
    if not candles:
        raise LiveError("Kapanmış mum gelmedi")
    last = max(candles)
    return (f"Bağlantı tamam: data-api.binance.vision; son kapanan BTCUSDT 1s mum {last} "
            f"kapanış {candles[last].close} ({(now - last).total_seconds() / 60:.0f} dk önce)")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m jev.live",
        description="Canlı SANAL işlem: gerçek zamanlı Binance fiyatı, sahte para. Emir göndermez.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="Binance halka açık veriye erişimi dene")
    p_init = sub.add_parser("init", help="Yeni sanal hesap başlat ve stratejiyi ısındır")
    p_run = sub.add_parser("run", help="Yeni kapanan mumları işle (zamanlayıcıdan çağrılır)")
    p_status = sub.add_parser("status", help="Durum, performans ve karar isabeti")
    p_golge = sub.add_parser("golge", help="Jev gölge modu tahminlerinin isabet raporu")
    p_golge.add_argument("--dir", required=True, type=Path, help="Durum klasörü")
    p_golge.add_argument("--csv", type=Path, help="Sonuçları bu CSV dosyasına da yaz")
    p_dene = sub.add_parser("golge-dene", help="Tek Jev çağrısıyla bağlantıyı dene (ücretli)")
    p_dene.add_argument("--dir", required=True, type=Path, help="Durum klasörü")
    for p in (p_init, p_run, p_status):
        p.add_argument("--dir", required=True, type=Path, help="Durum klasörü")
    p_status.add_argument("--horizon", type=int, default=24)
    p_run.add_argument("--catchup", type=int, default=48,
                       help="Kesinti sonrası en fazla kaç mum geriye bakılsın")
    p_init.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"])
    p_init.add_argument("--interval", default="1h", choices=sorted(INTERVALS))
    p_init.add_argument("--strategy", choices=("sma", "al-tut"), default="sma")
    p_init.add_argument("--fast", type=int, default=24)
    p_init.add_argument("--slow", type=int, default=96)
    p_init.add_argument("--fraction", default="0.95")
    p_init.add_argument("--vol-target", default="0.01",
                        help="Oynaklığa göre pozisyon hedefi (boş bırakmak için '')")
    p_init.add_argument("--vol-window", type=int, default=72)
    p_init.add_argument("--stop-loss-pct")
    p_init.add_argument("--take-profit-pct")
    p_init.add_argument("--cash", default="10000")
    p_init.add_argument("--taker-rate", default="0.001")
    p_init.add_argument("--slippage-bps", default="5")
    p_init.add_argument("--max-volume-share", default="0.01")
    p_init.add_argument("--rules", default=str(Path(__file__).resolve().parent.parent
                                               / "data" / "exchange_info_sample.json"))
    p_init.add_argument("--max-trade-notional", help="İşlem başına azami tutar (USDT)")
    p_init.add_argument("--max-position-notional", help="Tek coinde azami pozisyon (USDT)")
    p_init.add_argument("--min-cash-reserve", help="Her zaman nakitte kalacak tutar (USDT)")
    p_init.add_argument("--max-lag-bars", type=int, default=2,
                        help="Bundan eski barlarla işlem yapılmaz")
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            print(check())
        elif args.command == "init":
            settings = {k: getattr(args, k) for k in (
                "symbols", "interval", "strategy", "fast", "slow", "fraction", "vol_target",
                "vol_window", "stop_loss_pct", "take_profit_pct", "cash", "taker_rate",
                "slippage_bps", "max_volume_share", "rules", "max_trade_notional",
                "max_position_notional", "min_cash_reserve", "max_lag_bars")}
            init(args.dir, settings)
            print(status(args.dir))
        elif args.command == "run":
            run_once(args.dir, catchup=args.catchup)
        elif args.command == "golge":
            print(shadow_report(args.dir, args.csv))
        elif args.command == "golge-dene":
            print(shadow_try(args.dir))
        else:
            print(status(args.dir, args.horizon))
    except (LiveError, ValueError, OSError, jev_golge.ShadowError) as exc:
        parser.exit(1, f"Hata: {exc}\n")


if __name__ == "__main__":
    # `python -m jev.live` bu dosyayı `__main__` olarak çalıştırır. Kaydedilen nesnelerin
    # sınıfı her zaman `jev.live` adıyla saklansın diye asıl modül üzerinden çalıştır.
    from jev.live import main as _main
    _main()
