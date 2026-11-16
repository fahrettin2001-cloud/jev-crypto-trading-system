"""Eleştirmen girdisi: YALNIZCA eğitim seti. Bölüm özeti + tahmin + gerçek sonuç."""
import json, sys
from pathlib import Path
B = Path(__file__).parent
tur = sys.argv[1]
eps = {e["id"]: e for e in json.load(open(B / "egitim.json"))}
ans = {m["id"]: m for m in json.load(open(B / "gizli" / "egitim_cevap.json"))}
preds = {r["id"]: r for r in json.load(open(B / "tahmin" / f"egitim_tur{tur}.json"))}
rows = []
for i, e in eps.items():
    p = preds.get(i, {}).get("p")
    if p is None:
        continue
    m = ans[i]
    ozet = {k: v for k, v in e.items() if k != "fiyatlar_son90gun"}
    f = e["fiyatlar_son90gun"]
    ozet["fiyat_ozeti(her 10 gunde bir)"] = f[::10] + [f[-1]]
    rows.append({**ozet, "tahmin_p": p, "tahmin_nedeni": preds[i].get("neden", ""),
                 "GERCEK_20g_sonra_yukari_mi": m["yukari"], "GERCEK_20g_getiri_%": round(100 * m["getiri_20g"], 1),
                 "brier_katkisi": round((p - m["yukari"]) ** 2, 3)})
rows.sort(key=lambda r: -r["brier_katkisi"])
(B / f"elestiri_girdi_tur{tur}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=0))
print(len(rows), "satır")
