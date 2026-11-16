"""Sinyal laboratuvarı: grafikte "nelere bakmalı?" sorusunu binlerce örnekte ölçer.

Her aday sinyal, her coin ve her gün için YALNIZCA o güne kadarki kapanışlarla
hesaplanır. Ölçüm: sinyal ile gelecek 5/20/60 günlük getiri arasındaki sıra
korelasyonu (Spearman). İki türlü:
- zaman serisi (ts): getiri ham; "bu sinyal piyasa zamanlamasında işe yarar mı?"
- kesitsel (ks): o günün coin ortalaması çıkarılmış getiri; "hangi coin diğerlerinden
  iyi gider?" (her gün coinler arası sıra korelasyonu, sonra ortalama)
Örtüşen pencereler istatistiği şişirmesin diye t değeri yalnızca H günde bir alınan
örneklerle hesaplanır. Dönemler: eğitim 2020-01→2022-12, doğrulama 2023,
sınav 2024-01→veri sonu. Bir sinyal "sağlam" sayılır: eğitimde |t|≥3 (çoklu test
için sıkı eşik), doğrulama ve sınavda aynı işaret ve |t|≥1.5.

Kullanım: python3 lab.py <veri/genis/kripto klasörü> [--out rapor.md]
"""
import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd

DONEMLER = {"egitim": ("2020-01-01", "2022-12-31"), "dogrulama": ("2023-01-01", "2023-12-31"),
            "sinav": ("2024-01-01", "2100-01-01")}
UFUKLAR = (5, 20, 60)


def yukle(klasor: Path) -> pd.DataFrame:
    seriler = {}
    for p in sorted(klasor.glob("*.csv")):
        s = pd.read_csv(p, parse_dates=["gun"]).set_index("gun")["kapanis"]
        seriler[p.stem.replace("USDT", "")] = s
    px = pd.DataFrame(seriler).sort_index()
    # Çıkarılan coin: son verisinden sonrası NaN kalır (ileri doldurma YOK)
    return px


# --- aday sinyaller (hepsi yalnızca geçmişi kullanır) --------------------------

def ozellikler(px: pd.DataFrame) -> dict[str, tuple[str, pd.DataFrame]]:
    r = np.log(px).diff()
    btc = px["BTC"]
    f = {}
    def add(ad, tur, df): f[ad] = (tur, df)
    for n in (7, 30, 90, 180):
        add(f"getiri_{n}g", "ts", px / px.shift(n) - 1)
    add("getiri_90g_son30_haric", "ts", px.shift(30) / px.shift(90) - 1)
    for n in (50, 100, 200):
        add(f"sma{n}_uzaklik", "ts", px / px.rolling(n).mean() - 1)
    add("zirve_365_uzaklik", "ts", px / px.rolling(365, min_periods=200).max() - 1)
    add("dip_365_uzaklik", "ts", px / px.rolling(365, min_periods=200).min() - 1)
    add("kirilim_20g", "ts", px / px.rolling(20).max().shift(1) - 1)
    add("oynaklik_30g", "ts", r.rolling(30).std())
    add("oynaklik_sikisma", "ts", r.rolling(10).std() / r.rolling(90).std())
    add("max_gunluk_getiri_30g", "ts", r.rolling(30).max())
    # RSI 14 (Wilder yaklaşık)
    up = r.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-r.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    add("rsi14", "ts", 100 - 100 / (1 + up / dn))
    # Trend kuralları toplamı (0..4)
    s = lambda n: px.rolling(n).mean()
    tr = ((s(10) > s(40)).astype(float) + (s(20) > s(100)).astype(float)
          + (px > s(50)).astype(float) + (px > s(100)).astype(float)).where(px.notna())
    add("trend_kural_sayisi", "ts", tr)
    # Piyasa (BTC) bağlamı — her coin için aynı değer
    for ad, seri in (("btc_getiri_30g", btc / btc.shift(30) - 1),
                     ("btc_sma100_uzaklik", btc / btc.rolling(100).mean() - 1)):
        add(ad, "ts", pd.DataFrame({c: seri for c in px.columns}).where(px.notna()))
    # BTC'ye göre göreli güç
    add("goreli_guc_30g_btc", "ts", (px / px.shift(30)).div(btc / btc.shift(30), axis=0) - 1)
    # Kesitsel sıralar (o gün coinler arasında)
    for n in (7, 30, 90):
        add(f"ks_sira_getiri_{n}g", "ks", (px / px.shift(n) - 1).rank(axis=1, pct=True))
    add("ks_sira_oynaklik_30g", "ks", r.rolling(30).std().rank(axis=1, pct=True))
    add("ks_sira_zirve_uzaklik", "ks", (px / px.rolling(365, min_periods=200).max() - 1).rank(axis=1, pct=True))
    add("ks_sira_max_getiri_30g", "ks", r.rolling(30).max().rank(axis=1, pct=True))
    return f


# --- ölçüm ----------------------------------------------------------------------

def gelecek(px: pd.DataFrame, h: int) -> pd.DataFrame:
    return px.shift(-h) / px - 1          # yalnızca hedef; sinyal hesabında kullanılmaz


def spearman_ts(x: pd.DataFrame, y: pd.DataFrame, h: int, a: str, b: str):
    """Havuzlanmış zaman serisi sıra korelasyonu; H günde bir örnek (örtüşme yok).
    Aynı gün coinler birlikte hareket ettiği için hata payı TARİHE GÖRE kümelenir
    (aksi halde 26 coin 26 bağımsız gözlem sanılır ve t şişer)."""
    parcalar = []
    for c in x.columns:
        d = pd.concat([x[c], y[c]], axis=1, keys=["x", "y"]).loc[a:b].dropna()
        parcalar.append(d)
    if not parcalar:
        return float("nan"), float("nan"), 0
    D = pd.concat(parcalar)
    gunler = sorted(D.index.unique())[::h]
    D = D[D.index.isin(gunler)]
    n = len(D)
    if n < 30 or len(gunler) < 10:
        return float("nan"), float("nan"), n
    zx = D["x"].rank(); zx = (zx - zx.mean()) / zx.std(ddof=0)
    zy = D["y"].rank(); zy = (zy - zy.mean()) / zy.std(ddof=0)
    z = zx * zy
    rho = float(z.mean())
    g = (z - rho).groupby(level=0).sum()          # tarih kümeleri
    se = math.sqrt(float((g ** 2).sum())) / n
    return rho, rho / se if se > 0 else float("nan"), n


def spearman_ks(x: pd.DataFrame, y: pd.DataFrame, h: int, a: str, b: str):
    """Kesitsel: her gün coinler arası sıra korelasyonu (getiri gün ortalamasından arındırılmış),
    H günde bir gün alınır; t = ort / (sd/√k)."""
    ydm = y.sub(y.mean(axis=1), axis=0)
    xs, ys = x.loc[a:b], ydm.loc[a:b]
    ics = []
    for gun in xs.index[::h]:
        d = pd.concat([xs.loc[gun], ys.loc[gun]], axis=1, keys=["x", "y"]).dropna()
        if len(d) >= 8:
            ics.append(d["x"].rank().corr(d["y"].rank()))
    k = len(ics)
    if k < 10:
        return float("nan"), float("nan"), k
    m, sd = float(np.mean(ics)), float(np.std(ics, ddof=1))
    return m, m / (sd / math.sqrt(k)) if sd > 0 else float("nan"), k


def calistir(px: pd.DataFrame, ek: dict | None = None) -> pd.DataFrame:
    feats = ozellikler(px)
    if ek:
        feats.update(ek)
    satirlar = []
    for h in UFUKLAR:
        y = gelecek(px, h)
        for ad, (tur, x) in feats.items():
            sat = {"sinyal": ad, "tur": tur, "ufuk": h}
            for dn, (a, b) in DONEMLER.items():
                fn = spearman_ks if tur == "ks" else spearman_ts
                rho, t, n = fn(x, y, h, a, b)
                sat[f"{dn}_rho"], sat[f"{dn}_t"], sat[f"{dn}_n"] = rho, t, n
            e, d, s = sat["egitim_t"], sat["dogrulama_t"], sat["sinav_t"]
            sat["saglam"] = bool(abs(e) >= 3 and np.sign(d) == np.sign(e) == np.sign(s)
                                 and abs(d) >= 1.5 and abs(s) >= 1.5)
            satirlar.append(sat)
    return pd.DataFrame(satirlar)


def rapor(df: pd.DataFrame) -> str:
    fmt = lambda v: "—" if pd.isna(v) else f"{v:+.3f}"
    ft = lambda v: "—" if pd.isna(v) else f"{v:+.1f}"
    out = ["# Sinyal laboratuvarı", "",
           f"{df['sinyal'].nunique()} aday sinyal × {len(UFUKLAR)} ufuk = {len(df)} test. "
           "Sağlam: eğitimde |t|≥3, doğrulama ve sınavda aynı yön ve |t|≥1,5.", "",
           "| Sinyal | Tür | Ufuk | Eğitim ρ (t) | Doğrulama ρ (t) | Sınav ρ (t) | Sağlam |",
           "|---|---|---|---|---|---|---|"]
    for _, r in df.sort_values(["saglam", "egitim_t"], key=lambda s: s.abs() if s.name == "egitim_t" else s,
                               ascending=False).iterrows():
        out.append(f"| {r.sinyal} | {r.tur} | {r.ufuk}g | {fmt(r.egitim_rho)} ({ft(r.egitim_t)}) | "
                   f"{fmt(r.dogrulama_rho)} ({ft(r.dogrulama_t)}) | {fmt(r.sinav_rho)} ({ft(r.sinav_t)}) | "
                   f"{'EVET' if r.saglam else ''} |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("veri", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    df = calistir(yukle(a.veri))
    txt = rapor(df)
    if a.out:
        a.out.write_text(txt, encoding="utf-8")
        df.to_csv(a.out.with_suffix(".csv"), index=False)
    print(txt)
