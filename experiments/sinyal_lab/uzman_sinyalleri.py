"""Uzman ajanların önerdiği sinyaller (16 Kasım 2026, test EDİLMEDEN önce sabitlendi).
Teknik analist (TA) ve kantitatif araştırmacı (KA) önerileri; yalnızca kapanış ile
hesaplanabilenler. Hacim/yüksek/düşük gerektirenler (CLV, ATR kırılımı, hacim z,
Amihud, VWAP sapması) veri olmadığı için ertelendi. range_compress_60 yön
belirtmediği (yalnızca büyüklük) için yön testine alınmadı."""
import numpy as np
import pandas as pd


def _beta(r, rb, w):
    cov = (r.mul(rb, axis=0)).rolling(w).mean() - r.rolling(w).mean().mul(rb.rolling(w).mean(), axis=0)
    return cov.div(rb.rolling(w).var(ddof=0), axis=0)


def _streak(s: pd.Series) -> pd.Series:
    out, cur, prev = [], 0, None
    for v in s.diff():
        if pd.isna(v) or v == 0:
            cur = 0
        elif v > 0:
            cur = cur + 1 if cur > 0 else 1
        else:
            cur = cur - 1 if cur < 0 else -1
        out.append(cur)
    return pd.Series(out, index=s.index, dtype=float)


def _aroon(s: pd.Series, n=25) -> pd.Series:
    up = s.rolling(n + 1).apply(lambda a: 100 * (n - (n - int(np.argmax(a)))) / n, raw=True)
    dn = s.rolling(n + 1).apply(lambda a: 100 * (n - (n - int(np.argmin(a)))) / n, raw=True)
    return up - dn


def uzman_ozellikleri(px: pd.DataFrame) -> dict:
    r = np.log(px).diff()
    rb = r["BTC"]
    btc = px["BTC"]
    lp = np.log(px)
    f = {}
    def add(ad, tur, df): f[ad] = (tur, df.where(px.notna()))
    # --- Teknik analist ---
    add("TA_roc_20", "ts", px / px.shift(20) - 1)
    add("TA_dist_high_60", "ts", px / px.rolling(60).max() - 1)
    add("TA_zscore_rev_20", "ts", (px - px.rolling(20).mean()) / px.rolling(20).std())
    ema12, ema26 = px.ewm(span=12, adjust=False).mean(), px.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    add("TA_macd_hist_norm", "ts", (macd - macd.ewm(span=9, adjust=False).mean()) / px)
    ema50 = px.ewm(span=50, adjust=False).mean()
    add("TA_ema_slope_50", "ts", ema50 / ema50.shift(10) - 1)
    add("TA_streak", "ts", px.apply(_streak))
    add("TA_btc_relstr_60", "ts", (px / px.shift(60)).div(btc / btc.shift(60), axis=0) - 1)
    b120 = _beta(r, rb, 120)
    add("TA_btc_resid_rev_5", "ts", (px / px.shift(5) - 1) - b120.mul(btc / btc.shift(5) - 1, axis=0))
    add("TA_xsec_rank_mom_20", "ks", (px / px.shift(20) - 1).rank(axis=1, pct=True))
    add("TA_aroon_osc_25", "ts", px.apply(_aroon))
    # --- Kantitatif araştırmacı ---
    add("KA_tsmom_90_isaret", "ts", np.sign(lp - lp.shift(90)))
    add("KA_tsmom_90_oynaklik_olcekli", "ts", (lp - lp.shift(90)) / (r.rolling(60).std() * np.sqrt(90)))
    add("KA_ma_cross_20_100", "ts", px.rolling(20).mean() / px.rolling(100).mean() - 1)
    add("KA_neg_skew_60", "ts", -r.rolling(60).skew())
    add("KA_ara_momentum_skip30", "ts", lp.shift(30) - lp.shift(252))
    add("KA_ks_mom_28", "ks", (lp - lp.shift(28)).rank(axis=1, pct=True))
    add("KA_ks_kisa_donus_5", "ks", (-(lp - lp.shift(5))).rank(axis=1, pct=True))
    b180 = _beta(r, rb, 180)
    resid90 = r.rolling(90).sum() - b180.mul(rb.rolling(90).sum(), axis=0)
    add("KA_ks_artik_mom_90", "ks", resid90.rank(axis=1, pct=True))
    add("KA_ks_dusuk_beta_120", "ks", (-b120).rank(axis=1, pct=True))
    b60 = _beta(r, rb, 60)
    idv = np.sqrt((r.rolling(60).var(ddof=0) - (b60 ** 2).mul(rb.rolling(60).var(ddof=0), axis=0)).clip(lower=0))
    add("KA_ks_dusuk_idio_oynaklik_60", "ks", (-idv).rank(axis=1, pct=True))
    add("KA_ks_neg_max_30", "ks", (-r.rolling(30).max()).rank(axis=1, pct=True))
    return f
