"""Anonim grafik bölümleri: tarih ve coin adı yok, fiyat son kapanış=100'e ölçekli.
Hedef (gizli): 20 gün sonraki kapanış bugünkünden yüksek mi."""
import csv, json, random, statistics, sys
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jev.duygu import trend_weights

VERI = Path(sys.argv[1] if len(sys.argv) > 1 else "veri/genis/kripto")  # sonuç deposundaki veri/genis/kripto
OUT = Path(__file__).parent
(OUT / "gizli").mkdir(exist_ok=True)
H, SHOW = 20, 90
SETS = {"egitim": (date(2020, 6, 1), date(2022, 12, 31), 40, 1),
        "dogrulama": (date(2023, 1, 1), date(2023, 12, 31), 40, 2),
        "sinav": (date(2024, 1, 1), date(2026, 10, 31), 60, 3)}

def read(p):
    with open(p) as f:
        r = sorted((date.fromisoformat(x["gun"]), float(x["kapanis"])) for x in csv.DictReader(f))
    return [d for d, _ in r], [c for _, c in r]

data = {p.stem: read(p) for p in sorted(VERI.glob("*.csv"))}
btc_d, btc_c = data["BTCUSDT"]; btc_w = trend_weights(btc_c); btc_i = {d: i for i, d in enumerate(btc_d)}

def rules(c, i):
    def sma(n): return sum(c[i - n + 1:i + 1]) / n
    return {"SMA10>SMA40": sma(10) > sma(40), "SMA20>SMA100": sma(20) > sma(100),
            "fiyat>SMA50": c[i] > sma(50), "fiyat>SMA100": c[i] > sma(100)}

def episode(sym, i):
    d, c = data[sym]
    w = trend_weights(c)[i]
    seg = c[i - SHOW + 1:i + 1]
    k = 100 / c[i]
    rets = [c[j] / c[j - 1] - 1 for j in range(i - 29, i + 1)]
    bi = btc_i.get(d[i])
    ep = {
        "fiyatlar_son90gun": [round(x * k, 1) for x in seg],
        "getiri_30g_%": round((c[i] / c[i - 30] - 1) * 100, 1),
        "getiri_90g_%": round((c[i] / c[i - 90] - 1) * 100, 1),
        "SMA50'ye_uzaklik_%": round((c[i] / (sum(c[i-49:i+1]) / 50) - 1) * 100, 1),
        "SMA100'e_uzaklik_%": round((c[i] / (sum(c[i-99:i+1]) / 100) - 1) * 100, 1),
        "gunluk_oynaklik_30g_%": round(statistics.pstdev(rets) * 100, 2),
        "1yillik_zirveden_uzaklik_%": round((c[i] / max(c[max(0, i - 365):i + 1]) - 1) * 100, 1),
        "trend_kurallari": {k2: bool(v) for k2, v in rules(c, i).items()},
        "piyasa_lideri_30g_getiri_%": round((btc_c[bi] / btc_c[bi - 30] - 1) * 100, 1) if bi else None,
        "piyasa_lideri_trend_agirligi": btc_w[bi] if bi else None,
    }
    up = c[i + H] > c[i]
    meta = {"sembol": sym, "gun": d[i].isoformat(), "yukari": up,
            "getiri_20g": c[i + H] / c[i] - 1, "trend_agirligi": w}
    return ep, meta

for name, (a, b, n, seed) in SETS.items():
    rnd = random.Random(seed); eps, metas, used = [], [], set()
    cands = []
    for sym, (d, c) in data.items():
        for i in range(150, len(d) - H):
            if a <= d[i] and d[i + H] <= b:
                cands.append((sym, i))
    rnd.shuffle(cands)
    for sym, i in cands:
        if any(s == sym and abs(i - j) < 30 for s, j in used):
            continue
        used.add((sym, i))
        ep, meta = episode(sym, i)
        ep = {"id": f"{name[0].upper()}{len(eps)+1:02d}", **ep}
        eps.append(ep); metas.append({"id": ep["id"], **meta})
        if len(eps) == n: break
    (OUT / f"{name}.json").write_text(json.dumps(eps, ensure_ascii=False))
    (OUT / "gizli" / f"{name}_cevap.json").write_text(json.dumps(metas, ensure_ascii=False))
    ups = sum(m["yukari"] for m in metas)
    print(name, len(eps), "bölüm, yukarı oranı", round(ups / len(eps), 2),
          "coin sayısı", len({m["sembol"] for m in metas}))
