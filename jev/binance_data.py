"""Binance Global halka açık verisini indirme aracı (anahtar gerektirmez).

Bu modül yalnızca `python -m jev.binance_data ...` ile açıkça çalıştırıldığında
ağa çıkar; backtest ve diğer modüller ağ kullanmaz. Hesap, API anahtarı veya
emir yolu içermez.

İndirilenler:
- İşlem kuralları: `GET /api/v3/exchangeInfo` (api.binance.com, olmazsa
  data-api.binance.vision) → `exchange_info.json`
- Geçmiş mumlar: data.binance.vision aylık kline arşivleri. Her zip,
  yanındaki `.CHECKSUM` dosyasındaki SHA-256 ile doğrulanır; uyuşmazsa
  dosya yazılmaz.

Örnek:
    python -m jev.binance_data --symbols BTCUSDT ETHUSDT --interval 1h \\
        --start 2026-08 --end 2026-10
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Iterable

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "data" / "binance"
EXCHANGE_INFO_HOSTS = ("https://api.binance.com", "https://data-api.binance.vision")
VISION = "https://data.binance.vision/data/spot/monthly/klines"
INTERVALS = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"}
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{5,20}$")
_MONTH_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")

Fetch = Callable[[str], bytes]


class DownloadError(RuntimeError):
    pass


def http_fetch(url: str, timeout: float = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "jev-crypto-trading-system/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise DownloadError(f"{url}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise DownloadError(f"{url}: {exc.reason}") from exc


def _check_symbols(symbols: Iterable[str]) -> list[str]:
    out = []
    for s in symbols:
        if not _SYMBOL_RE.match(s):
            raise ValueError(f"Geçersiz sembol: {s!r} (ör. BTCUSDT)")
        out.append(s)
    if not out:
        raise ValueError("En az bir sembol gerekli")
    return out


def months_between(start: str, end: str) -> list[str]:
    """'2026-08', '2026-10' → ['2026-08', '2026-09', '2026-10']"""
    ms, me = _MONTH_RE.match(start), _MONTH_RE.match(end)
    if not ms or not me:
        raise ValueError("Ay biçimi YYYY-AA olmalı")
    y, m = int(ms[1]), int(ms[2])
    ye, me_ = int(me[1]), int(me[2])
    if (y, m) > (ye, me_):
        raise ValueError("Başlangıç ayı bitişten sonra olamaz")
    out = []
    while (y, m) <= (ye, me_):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    if len(out) > 60:
        raise ValueError("En fazla 60 ay indirilebilir")
    return out


def download_exchange_info(symbols: Iterable[str], out_dir: Path, fetch: Fetch = http_fetch) -> Path:
    symbols = _check_symbols(symbols)
    query = urllib.parse.urlencode({"symbols": json.dumps(symbols, separators=(",", ":"))})
    errors = []
    for host in EXCHANGE_INFO_HOSTS:
        url = f"{host}/api/v3/exchangeInfo?{query}"
        try:
            data = json.loads(fetch(url))
        except (DownloadError, ValueError) as exc:
            errors.append(str(exc))
            continue
        got = {s.get("symbol") for s in data.get("symbols", [])} if isinstance(data, dict) else set()
        if not set(symbols) <= got:
            errors.append(f"{url}: eksik semboller {sorted(set(symbols) - got)}")
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "exchange_info.json"
        path.write_text(json.dumps(data, indent=1), encoding="utf-8")
        return path
    raise DownloadError("exchangeInfo indirilemedi: " + "; ".join(errors))


def download_month(symbol: str, interval: str, month: str, out_dir: Path,
                   fetch: Fetch = http_fetch, force: bool = False) -> Path:
    (symbol,) = _check_symbols([symbol])
    if interval not in INTERVALS:
        raise ValueError(f"Geçersiz aralık: {interval}")
    if not _MONTH_RE.match(month):
        raise ValueError("Ay biçimi YYYY-AA olmalı")
    name = f"{symbol}-{interval}-{month}"
    target = out_dir / f"{name}.csv"
    if target.exists() and not force:
        return target
    url = f"{VISION}/{symbol}/{interval}/{name}.zip"
    checksum_text = fetch(url + ".CHECKSUM").decode("utf-8", "replace").split()
    if len(checksum_text) < 1 or not re.fullmatch(r"[0-9a-f]{64}", checksum_text[0]):
        raise DownloadError(f"{url}.CHECKSUM beklenen biçimde değil")
    blob = fetch(url)
    actual = hashlib.sha256(blob).hexdigest()
    if actual != checksum_text[0]:
        raise DownloadError(f"{name}.zip SHA-256 uyuşmuyor (beklenen {checksum_text[0]}, "
                            f"gelen {actual}); dosya yazılmadı")
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            members = zf.namelist()
            if members != [f"{name}.csv"]:
                raise DownloadError(f"{name}.zip beklenmeyen içerik: {members}")
            if zf.getinfo(members[0]).file_size > 500 * 1024 * 1024:
                raise DownloadError(f"{name}.csv çok büyük")
            content = zf.read(members[0])
    except zipfile.BadZipFile as exc:
        raise DownloadError(f"{name}.zip bozuk") from exc
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".csv.tmp")
    tmp.write_bytes(content)
    # Okunabildiğini doğrula; değilse bırakma
    from .klines import load_binance_klines
    try:
        load_binance_klines(tmp)
    except ValueError:
        tmp.unlink()
        raise
    tmp.replace(target)
    return target


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m jev.binance_data",
        description="Binance Global halka açık verisini indirir (anahtarsız, salt okunur).")
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"])
    parser.add_argument("--interval", default="1h", choices=sorted(INTERVALS))
    parser.add_argument("--start", help="İlk ay, YYYY-AA")
    parser.add_argument("--end", help="Son ay, YYYY-AA (aylık arşiv ay bitince yayımlanır)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--no-exchange-info", action="store_true")
    parser.add_argument("--force", action="store_true", help="Var olan dosyaları yeniden indir")
    args = parser.parse_args(argv)
    if bool(args.start) != bool(args.end):
        parser.error("--start ve --end birlikte verilmeli")

    try:
        symbols = _check_symbols(args.symbols)
        files: dict[str, list[Path]] = {s: [] for s in symbols}
        if not args.no_exchange_info:
            print(f"Yazıldı: {download_exchange_info(symbols, args.out)}")
        if args.start:
            for month in months_between(args.start, args.end):
                for s in symbols:
                    path = download_month(s, args.interval, month, args.out, force=args.force)
                    files[s].append(path)
                    print(f"Doğrulandı ve yazıldı: {path}")
    except (DownloadError, ValueError, OSError) as exc:
        parser.exit(1, f"Hata: {exc}\n")

    if args.start:
        paths = [str(p) for s in symbols for p in files[s]]
        syms = [s for s in symbols for _ in files[s]]
        rules = f" --rules {args.out / 'exchange_info.json'}" if not args.no_exchange_info else ""
        print("\nBacktest için:")
        print(f"python -m jev.backtest --symbol {symbols[0]} --prices {' '.join(paths)} "
              f"--kline-symbols {' '.join(syms)}{rules}")


if __name__ == "__main__":
    main()
