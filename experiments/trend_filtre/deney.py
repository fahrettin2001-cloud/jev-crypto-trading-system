"""Trend + idiosenkratik oynaklık filtresi (ön kayıt: 16 Kasım 2026, çalıştırmadan önce).

Soru: Trend kurallarını yalnızca kendine özgü (BTC'den bağımsız) oynaklığı en düşük
K coinde uygulamak, BTC+ETH trendinden daha iyi mi?
- Taban: BTC+ETH trend (her birine 1/2 pay × trend ağırlığı).
- Varyant K ∈ {2, 3, 5, 8}: her 20 günde bir, o güne kadarki 60 günlük veriyle
  idiosenkratik oynaklığı en düşük K coin seçilir (BTC'nin BTC'ye göre artığı 0'dır,
  yani BTC her zaman seçilir). Seçilenlere 1/K pay × trend ağırlığı.
- Ağırlıklar fiyatla kayar, hedeften payın %10'undan fazla sapınca düzeltilir.
- Masraf: her ağırlık değişiminde %0,25. Karar kapanışta, uygulama ertesi gün.
- Seçim: eğitim (2020-01 → 2023-12) Sharpe'ına göre tek varyant; test 2024-01 →.
Kullanım: python3 deney.py <veri/genis klasörü>
"""
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jev import genis_tarama as G  # noqa: E402

KLER = (2, 3, 5, 8)
YENIDEN_SECIM = 20


def idio_vol(px: pd.DataFrame, w=60) -> pd.DataFrame:
    r = np.log(px).diff()
    rb = r["BTCUSDT"]
    cov = r.mul(rb, axis=0).rolling(w).mean() - r.rolling(w).mean().mul(rb.rolling(w).mean(), axis=0)
    beta = cov.div(rb.rolling(w).var(ddof=0), axis=0)
    return np.sqrt((r.rolling(w).var(ddof=0) - (beta ** 2).mul(rb.rolling(w).var(ddof=0), axis=0)).clip(lower=0))


class Filtreli(G.Universe):
    def __init__(self, prices, k):
        super().__init__(prices)
        self.k = k
        px = pd.DataFrame({s: pd.Series(p) for s, p in prices.items()}).sort_index()
        px.index = pd.to_datetime(px.index)
        self.iv = idio_vol(px)
        self.secim, self._son = (), -10**9

    def targets(self, i, v, buy_hold=False, only=None):
        if only is not None or buy_hold:
            return super().targets(i, v, buy_hold, only)
        if i - self._son >= YENIDEN_SECIM:
            gun = pd.Timestamp(self.calendar[i])
            row = self.iv.loc[:gun].iloc[-1] if gun >= self.iv.index[0] else pd.Series(dtype=float)
            aktif = [s for s in self.syms if self.ready[s][i] and pd.notna(row.get(s))]
            self.secim = tuple(sorted(aktif, key=lambda s: row[s])[: self.k])
            self._son = i
        sec = [s for s in self.secim if self.ready[s][i]]
        if not sec:
            return {}
        return {s: self.weight[s][i] / self.k for s in sec}


def main(veri: Path):
    prices = {s: G._read(veri / "kripto" / f"{s}.csv") for s in G.EVRENLER["kripto"][1]
              if (veri / "kripto" / f"{s}.csv").exists()}
    tr = (date(2020, 1, 1), date(2023, 12, 31))
    base = G.Universe(prices)
    last = base.calendar[-1]
    te = (date(2024, 1, 1), last)
    sim = lambda u, a, b, **kw: u.simulate(G.Variant(), a, b, 0.0025, 365, **kw)
    satir = lambda ad, r: f"| {ad} | {r.total*100:+.1f}% | {r.max_dd*100:.1f}% | {r.sharpe:.2f} | %{r.cost*100:.1f} | %{r.exposure*100:.0f} |"
    print("| Strateji | Toplam | En büyük düşüş | Sharpe | Masraf | Ort. yatırım |\n|---|---|---|---|---|---|")
    sonuc = {}
    for donem, (a, b) in (("EĞİTİM", tr), ("TEST", te)):
        print(f"| **{donem}** | | | | | |")
        print(satir("BTC+ETH trend (taban)", sim(base, a, b, only=("BTCUSDT", "ETHUSDT"))))
        for k in KLER:
            r = sim(Filtreli(prices, k), a, b)
            sonuc[(donem, k)] = r
            print(satir(f"Trend, en düşük idio-oynaklık {k} coin", r))
    secilen = max(KLER, key=lambda k: sonuc[("EĞİTİM", k)].sharpe)
    print(f"\nEğitimde seçilen K={secilen}; testte Sharpe {sonuc[('TEST', secilen)].sharpe:.2f}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
