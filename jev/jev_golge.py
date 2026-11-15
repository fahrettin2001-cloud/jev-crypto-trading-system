"""Jev gölge modu: canlı sanal işlem yanında, KARARLARI DEĞİŞTİRMEDEN olasılık kaydı.

Soru (sabit anlam, çevrimdışı `jev.shadow` ile aynı):

    P( `ufuk_bar` bar sonraki kapanış  >  tahmin anındaki kapanış )

- "Tahmin anı" en son kapanan mumun kapanış zamanıdır (`tahmin_zamani`).
- "Hedef zaman" = tahmin_zamani + ufuk_bar × mum süresi (`hedef_zaman`).
  1 saatlik mumlarda varsayılan ufuk 24 bar = 24 saat sonra.
- Eşitlik veya düşüş = "yükselmedi" (0). Komisyon/kayma eşiği YOK; bu bir kâr
  ölçüsü değil, yön olasılığının ne kadar doğru ayarlandığının ölçüsüdür.
- `olasilik` 0..1 arası; 0,70 = "yükselme ihtimali %70".

Güvenlik ve yalıtım:
- İşlem durumu kaydedildikten SONRA çalışır; her hatası yutulur ve yalnızca
  günlüğe yazılır. Strateji bu modülü hiç görmez.
- Jev'e yalnızca halka açık Binance fiyatları gönderilir. Hesap, bakiye, işlem
  veya kişisel veri gönderilmez.
- API anahtarı koda, ayarlara ya da günlüğe yazılmaz; TypeSafe SDK'sı onu
  `TYPESAFE_API_KEY` ortam değişkeninden okur (sunucuda root'a ait ayrı dosya).
- Etkinleştirmek için durum klasörüne `jev_golge.json` koyulur; dosya yoksa kapalı.
  Ücret kontrolü: `her_n_bar` ve `gunluk_cagri_siniri`.

Kayıtlar: `golge.jsonl` (her satır bir tahmin). Rapor: `python -m jev.live golge`.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Sequence

CONFIG_FILE = "jev_golge.json"
LOG_FILE = "golge.jsonl"
RESULTS_FILE = "golge_sonuclar.csv"

# (sembol, [(kapanış zamanı, kapanış), ...] en eskiden en yeniye, ufuk_bar, mum süresi) -> olasılık
Predictor = Callable[[str, Sequence[tuple[datetime, Decimal]], int, timedelta], object]


class ShadowError(RuntimeError):
    pass


@dataclass(frozen=True)
class ShadowSettings:
    etkin: bool = False
    ufuk_bar: int = 24
    her_n_bar: int = 4                 # 1s mumda 4 = her 4 saatte bir tahmin
    gunluk_cagri_siniri: int = 24      # UTC günü başına toplam Jev çağrısı
    zaman_asimi_sn: float = 30.0
    gecmis_bar: int = 72               # Jev'e gönderilen son kapanış sayısı
    semboller: tuple[str, ...] | None = None   # None = botun tüm sembolleri
    model: str = "jev-latest"

    @classmethod
    def load(cls, directory: Path) -> "ShadowSettings":
        path = Path(directory) / CONFIG_FILE
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ShadowError(f"{CONFIG_FILE} bir JSON nesnesi olmalı")
        unknown = set(raw) - set(cls.__dataclass_fields__)
        if unknown:
            raise ShadowError(f"{CONFIG_FILE} içinde bilinmeyen alan: {sorted(unknown)}")
        if raw.get("semboller") is not None:
            raw["semboller"] = tuple(raw["semboller"])
        s = cls(**raw)
        for name in ("ufuk_bar", "her_n_bar", "gunluk_cagri_siniri", "gecmis_bar"):
            v = getattr(s, name)
            if type(v) is not int or v < 1:
                raise ShadowError(f"{name} pozitif tam sayı olmalı")
        if not 0 < float(s.zaman_asimi_sn) <= 120:
            raise ShadowError("zaman_asimi_sn 0..120 arası olmalı")
        return s


def parse_probability(value) -> Decimal:
    """Olasılığı doğrular; geçersizse ShadowError."""
    if isinstance(value, bool) or value is None:
        raise ShadowError(f"Geçersiz olasılık: {value!r}")
    try:
        p = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ShadowError(f"Geçersiz olasılık: {value!r}") from None
    if not p.is_finite() or not 0 <= p <= 1:
        raise ShadowError(f"Olasılık 0..1 dışında: {value!r}")
    return p


def call_with_timeout(fn: Callable[[], object], seconds: float):
    """`fn`'i arka plan iş parçacığında çalıştırır; süre aşılırsa ShadowError.
    İş parçacığı daemon olduğundan takılı bir çağrı programın bitmesini engellemez."""
    box: dict = {}

    def target():
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - çağırana taşınır
            box["error"] = exc

    t = threading.Thread(target=target, daemon=True, name="jev-golge")
    t.start()
    t.join(seconds)
    if t.is_alive():
        raise ShadowError(f"Jev {seconds:g} sn içinde cevap vermedi")
    if "error" in box:
        raise box["error"]
    return box.get("value")


# --- Jev (TypeSafe) bağdaştırıcısı --------------------------------------------------


def question_text(symbol: str, now_ts: datetime, price: Decimal, target_ts: datetime) -> str:
    return (f"Will the Binance {symbol} 1-candle close price at {target_ts:%Y-%m-%d %H:%M} UTC "
            f"be strictly higher than {price} (the close at {now_ts:%Y-%m-%d %H:%M} UTC)?")


def state_text(symbol: str, history: Sequence[tuple[datetime, Decimal]], step: timedelta,
               horizon: int) -> str:
    """Jev'e gönderilen durum metni: yalnızca halka açık fiyatlar."""
    last_ts, last = history[-1]
    first_ts, first = history[0]
    change = (last / first - 1) * 100
    minutes = int(step.total_seconds() // 60)
    closes = ", ".join(f"{c.normalize():f}" for _, c in history)
    return (f"Market: Binance spot {symbol}. Candle length: {minutes} minutes. "
            f"Last {len(history)} closes from {first_ts:%Y-%m-%d %H:%M} to {last_ts:%Y-%m-%d %H:%M} "
            f"UTC, oldest first: {closes}. Change over this window: {change:.2f}%. "
            f"Forecast horizon: {horizon} candles.")


def typesafe_predictor(model: str = "jev-latest", sdk=None) -> Predictor:
    """TypeSafe SDK'sı ile Jev System One tahmincisi. Anahtar yoksa ShadowError.

    `sdk` testler içindir (sahte modül); verilmezse `typesafe_sdk` içe aktarılır."""
    if not os.environ.get("TYPESAFE_API_KEY"):
        raise ShadowError("TYPESAFE_API_KEY yok")
    if sdk is None:
        try:
            import typesafe_sdk as sdk  # type: ignore[no-redef]
        except ImportError:
            raise ShadowError("typesafe-sdk kurulu değil") from None

    def predict(symbol, history, horizon, step):
        now_ts, price = history[-1]
        target = now_ts + horizon * step
        with sdk.TypeSafeClient(model=model) as client:
            response = client.system_one(
                state=state_text(symbol, history, step, horizon),
                questions={"yukselir": sdk.Noul(
                    instructions=question_text(symbol, now_ts, price, target))})
        return response.nouls["yukselir"].noul

    return predict


# --- kayıt ve değerlendirme ---------------------------------------------------------


def read_log(directory: Path) -> list[dict]:
    path = Path(directory) / LOG_FILE
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue   # yarım yazılmış satırı atla
    return out


def _append(directory: Path, record: dict) -> None:
    with open(Path(directory) / LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def record_predictions(directory: Path, closes: dict[str, list[tuple[datetime, Decimal]]],
                       symbols: Sequence[str], step: timedelta, now: datetime,
                       settings: ShadowSettings, predictor: Predictor,
                       max_lag: timedelta, log: Callable[[str], None] = lambda m: None) -> int:
    """En son kapanan mum için (koşullar uygunsa) her sembolde bir tahmin kaydeder.
    Kaydedilen tahmin sayısını döndürür. Hatalar sembol başına günlüğe yazılır."""
    directory = Path(directory)
    existing = read_log(directory)
    done = {(r.get("sembol"), r.get("tahmin_zamani")) for r in existing}
    today = now.date().isoformat()
    calls_today = sum(1 for r in existing if str(r.get("istek_zamani", "")).startswith(today))
    written = 0
    for symbol in (settings.semboller or symbols):
        series = closes.get(symbol) or []
        if len(series) < 2:
            continue
        ts, price = series[-1]
        if now - ts > max_lag:
            continue                                   # eski veriyle tahmin yok
        if int(ts.timestamp() // step.total_seconds()) % settings.her_n_bar:
            continue
        if (symbol, ts.isoformat()) in done:
            continue
        if calls_today >= settings.gunluk_cagri_siniri:
            log(f"Jev gölge: günlük çağrı sınırı ({settings.gunluk_cagri_siniri}) doldu")
            break
        history = series[-settings.gecmis_bar:]
        calls_today += 1
        started = time.monotonic()
        try:
            p = parse_probability(call_with_timeout(
                lambda: predictor(symbol, history, settings.ufuk_bar, step),
                settings.zaman_asimi_sn))
        except Exception as exc:  # noqa: BLE001 - gölge mod işlemi asla bozmaz
            log(f"Jev gölge: {symbol} tahmini alınamadı ({type(exc).__name__})")
            continue
        _append(directory, {
            "sembol": symbol,
            "tahmin_zamani": ts.isoformat(),
            "hedef_zaman": (ts + settings.ufuk_bar * step).isoformat(),
            "ufuk_bar": settings.ufuk_bar,
            "fiyat": str(price),
            "olasilik": str(p),
            "soru": "hedef_zaman kapanışı > tahmin_zamani kapanışı",
            "model": settings.model,
            "istek_zamani": now.isoformat(timespec="seconds"),
            "sure_ms": int((time.monotonic() - started) * 1000),
        })
        written += 1
    return written


@dataclass(frozen=True)
class Outcome:
    record: dict
    probability: Decimal
    outcome_price: Decimal | None
    increased: bool | None          # None = hedef zamana henüz gelinmedi / veri yok


def resolve(records: Sequence[dict], closes: dict[str, list[tuple[datetime, Decimal]]]
            ) -> list[Outcome]:
    lookup = {s: {t.isoformat(): c for t, c in series} for s, series in closes.items()}
    out = []
    for r in records:
        try:
            p = parse_probability(r["olasilik"])
            price = Decimal(r["fiyat"])
        except (KeyError, ShadowError, InvalidOperation):
            continue
        future = lookup.get(r.get("sembol"), {}).get(r.get("hedef_zaman"))
        out.append(Outcome(r, p, future, None if future is None else future > price))
    return out


def report(outcomes: Sequence[Outcome]) -> str:
    done = [o for o in outcomes if o.increased is not None]
    lines = ["Jev gölge modu (işlemleri ETKİLEMEZ)",
             "Soru: ufuk sonundaki kapanış, tahmin anındaki kapanıştan yüksek mi? "
             "'olasilik' = Jev'in 'evet' ihtimali.",
             f"Kayıtlı tahmin: {len(outcomes)}  sonuçlanan: {len(done)}  "
             f"bekleyen: {len(outcomes) - len(done)}"]
    if not done:
        lines.append("Henüz sonuçlanan tahmin yok.")
        return "\n".join(lines)
    n = len(done)
    brier = sum((o.probability - int(o.increased)) ** 2 for o in done) / n
    base = Decimal(sum(o.increased for o in done)) / n
    brier_base = sum((base - int(o.increased)) ** 2 for o in done) / n
    hits = sum((o.probability > Decimal("0.5")) == o.increased for o in done
               if o.probability != Decimal("0.5"))
    decided = sum(1 for o in done if o.probability != Decimal("0.5"))
    lines += [f"Brier puanı (düşük iyi): {brier:.4f}",
              f"  karşılaştırma — hep %50 diyen: 0.2500; dönemin yükseliş oranını "
              f"({base * 100:.0f}%) bilen: {brier_base:.4f}",
              f"Yön isabeti (%50 dışı tahminler): "
              + (f"{hits}/{decided} = {Decimal(hits) / decided * 100:.0f}%" if decided else "—")]
    if n < 30:
        lines.append(f"UYARI: az veri ({n} sonuç); en az 30-50 sonuç olmadan yorum yapmayın.")
    lines.append("Olasılık aralığı → gerçekleşen yükseliş oranı:")
    for lo in range(0, 100, 10):
        group = [o for o in done
                 if Decimal(lo) / 100 <= o.probability < Decimal(lo + 10) / 100
                 or (lo == 90 and o.probability == 1)]
        if group:
            rate = Decimal(sum(o.increased for o in group)) / len(group) * 100
            lines.append(f"  %{lo:>2}-%{lo + 10:<3}: {len(group):>3} tahmin, "
                         f"gerçekleşen %{rate:.0f}")
    return "\n".join(lines)


def outcome_rows(outcomes: Sequence[Outcome]) -> list[list]:
    return [[o.record.get("sembol"), o.record.get("tahmin_zamani"), o.record.get("hedef_zaman"),
             o.record.get("fiyat"), o.probability,
             "" if o.outcome_price is None else o.outcome_price,
             "bekliyor" if o.increased is None else int(o.increased)] for o in outcomes]


RESULT_HEADER = ["sembol", "tahmin_zamani", "hedef_zaman", "fiyat", "olasilik", "hedef_fiyat",
                 "yukseldi"]
