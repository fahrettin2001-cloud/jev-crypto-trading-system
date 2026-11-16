"""Hacim sinyallerini lab.py ölçümüyle çalıştırır (ön kayıtlı hacim_sinyalleri.py)."""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
import lab
from hacim_sinyalleri import hacim_ozellikleri


def yukle_ohlcv(k: Path):
    t = {}
    for p in sorted(k.glob("*.csv")):
        d = pd.read_csv(p, parse_dates=["gun"]).set_index("gun")
        t[p.stem.replace("USDT", "")] = d
    al = lambda col: pd.DataFrame({s: d[col] for s, d in t.items()}).sort_index().astype(float)
    return al("acilis"), al("yuksek"), al("dusuk"), al("kapanis"), al("hacim_usdt")


if __name__ == "__main__":
    o, h, l, c, v = yukle_ohlcv(Path(sys.argv[1]))
    feats = hacim_ozellikleri(o, h, l, c, v)
    import numpy as np
    rows = []
    for H in lab.UFUKLAR:
        y = lab.gelecek(c, H)
        for ad, (tur, x) in feats.items():
            r = {"sinyal": ad, "tur": tur, "ufuk": H}
            for dn, (a, b) in lab.DONEMLER.items():
                fn = lab.spearman_ks if tur == "ks" else lab.spearman_ts
                r[f"{dn}_rho"], r[f"{dn}_t"], r[f"{dn}_n"] = fn(x, y, H, a, b)
            e, d_, s = r["egitim_t"], r["dogrulama_t"], r["sinav_t"]
            r["saglam"] = bool(abs(e) >= 3 and np.sign(d_) == np.sign(e) == np.sign(s) and abs(d_) >= 1.5 and abs(s) >= 1.5)
            rows.append(r)
    df = pd.DataFrame(rows)
    txt = lab.rapor(df).replace("# Sinyal laboratuvarı", "# Hacim sinyalleri (ön kayıtlı)")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    if out:
        out.write_text(txt, encoding="utf-8"); df.to_csv(out.with_suffix(".csv"), index=False)
    print(txt)
