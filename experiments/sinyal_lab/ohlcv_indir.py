"""Binance günlük arşivinden 26 coin için açılış/yüksek/düşük/kapanış/hacim (USDT).
Önbellekte (genis_tarama'nın indirdiği aylık dosyalar) olan aylar yeniden indirilmez.
Kullanım (sunucu, jev kullanıcısı):
  python3 experiments/sinyal_lab/ohlcv_indir.py --onbellek HAM --out VERI/kripto_ohlcv
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jev.binance_data import DownloadError, download_month  # noqa: E402
from jev.genis_tarama import EVRENLER, _last_full_month, _months, _ONE_DAY  # noqa: E402
from jev.klines import load_binance_klines  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--onbellek", type=Path, required=True)
ap.add_argument("--out", type=Path, required=True)
ap.add_argument("--start", default="2019-06")
a = ap.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
for sym in EVRENLER["kripto"][1]:
    rows, missing, errors = {}, 0, []
    for m in _months(a.start, _last_full_month()):
        try:
            p = download_month(sym, "1d", m, a.onbellek / sym)
        except (DownloadError, OSError, ValueError) as exc:
            if "404" in str(exc):
                missing += 1
            else:
                errors.append(f"{m}: {exc}")
            continue
        for ct, c in load_binance_klines(p).items():
            rows[(ct - _ONE_DAY).date()] = (c.open, c.high, c.low, c.close, c.quote_volume)
    if not rows:
        print(f"{sym}: veri yok {errors[:1]}")
        continue
    with open(a.out / f"{sym}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["gun", "acilis", "yuksek", "dusuk", "kapanis", "hacim_usdt"])
        for d, v in sorted(rows.items()):
            w.writerow([d.isoformat(), *[str(x) if x is not None else "" for x in v]])
    print(f"{sym}: {len(rows)} gün, arşivi olmayan ay {missing}" + (f", HATA {errors[0]}" if errors else ""))
