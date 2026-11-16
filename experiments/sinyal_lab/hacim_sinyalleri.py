"""Hacim ve gün içi aralık sinyalleri — 16 Kasım 2026, VERİ GELMEDEN ÖNCE sabitlendi.

Kaynak: teknik analist uzman ajanın B listesi (5 sinyal) + baş eğitmenin "haber/ilgi
kaynaklı yükseliş" fikri için hacim vekilleri (4 sinyal). Hepsi yalnızca o güne
kadarki veriyi kullanır. Hacim = USDT cinsinden işlem hacmi (quote volume).
Ölçüm ve sağlamlık ölçütü lab.py ile aynı (tarihe göre kümelenmiş t; eğitimde |t|≥3,
doğrulama ve sınavda aynı yön ve |t|≥1,5)."""
import numpy as np
import pandas as pd


def hacim_ozellikleri(o, h, l, c, v):
    """o,h,l,c,v: tarih × coin DataFrame'leri."""
    r = c.pct_change()
    f = {}
    def add(ad, tur, df): f[ad] = (tur, df.where(c.notna()))
    rng = (h - l).replace(0, np.nan)
    # --- Teknik analist (B listesi) ---
    add("TA_clv_14", "ts", (((c - l) - (h - c)) / rng).rolling(14).mean())
    tr = pd.concat({k: x for k, x in (("a", h - l), ("b", (h - c.shift()).abs()), ("c", (l - c.shift()).abs()))}).groupby(level=1).max()
    atr14 = tr.rolling(14).mean()
    add("TA_atr_kirilim_20", "ts", (c - h.rolling(20).max().shift(1)) / atr14)
    add("TA_imzali_hacim_z_20", "ts", ((v - v.rolling(20).mean()) / v.rolling(20).std()) * np.sign(r))
    add("TA_amihud_20", "ts", (r.abs() / v.replace(0, np.nan)).rolling(20).mean())
    tp = (h + l + c) / 3
    vwap20 = (tp * v).rolling(20).sum() / v.rolling(20).sum()
    add("TA_vwap_sapma_20", "ts", c / vwap20 - 1)
    # --- Baş eğitmen: ilgi / haber vekilleri ---
    ilgi = v.rolling(7).mean() / v.rolling(90).mean()            # son hafta hacmi / 3 aylık
    add("BE_hacim_artisi_7_90", "ts", ilgi)
    add("BE_ks_hacim_artisi_sira", "ks", ilgi.rank(axis=1, pct=True))
    add("BE_hacimli_yukselis_7g", "ts", ilgi * (c / c.shift(7) - 1))   # hacimle gelen yükseliş
    add("BE_ks_hacim_payi_degisim_30", "ks",
        (v.div(v.sum(axis=1), axis=0).rolling(30).mean()
         / v.div(v.sum(axis=1), axis=0).rolling(30).mean().shift(30)).rank(axis=1, pct=True))
    return f
