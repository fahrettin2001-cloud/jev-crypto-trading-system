"""Tahminleri gizli cevaplarla puanlar. Kullanım: python3 puanla.py <set> <tahmin.json>"""
import json, sys
from pathlib import Path
B = Path(__file__).parent

def load(name): return {m["id"]: m for m in json.load(open(B / "gizli" / f"{name}_cevap.json"))}

def score(name, preds):
    ans = load(name)
    rows = [(float(preds[i]), ans[i]) for i in ans if i in preds]
    brier = sum((p - m["yukari"]) ** 2 for p, m in rows) / len(rows)
    acc = sum((p > 0.5) == m["yukari"] for p, m in rows) / len(rows)
    # olasılığa göre ağırlıklı "işlem": p>0.5 olanların ortalama 20g getirisi
    long = [m["getiri_20g"] for p, m in rows if p > 0.55]
    return {"n": len(rows), "brier": round(brier, 4), "isabet": round(acc, 3),
            "p>0.55_sayisi": len(long), "p>0.55_ort_20g_getiri_%": round(100 * sum(long) / len(long), 2) if long else None}

def baselines(name):
    tr = list(load("egitim").values()); ans = load(name)
    base = sum(m["yukari"] for m in tr) / len(tr)
    by = {}
    for m in tr: by.setdefault(m["trend_agirligi"], []).append(m["yukari"])
    rate = {w: (sum(v) + base * 4) / (len(v) + 4) for w, v in by.items()}  # küçültülmüş oran
    return {"taban_oran": score(name, {i: base for i in ans}),
            "hep_0.5": score(name, {i: 0.5 for i in ans}),
            "trend_kurali": score(name, {i: rate.get(m["trend_agirligi"], base) for i, m in ans.items()})}

if __name__ == "__main__":
    name = sys.argv[1]
    if len(sys.argv) > 2:
        raw = json.load(open(sys.argv[2]))
        preds = {r["id"]: r["p"] for r in raw}
        print(json.dumps(score(name, preds), ensure_ascii=False))
    else:
        print(json.dumps(baselines(name), ensure_ascii=False, indent=1))
