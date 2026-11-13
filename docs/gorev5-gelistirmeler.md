# Görev 5 — Botu geliştirme: ölçüm, risk ve yeni sinyaller

Sorumlu: @demirfahrieren-png (Claude ile). Başlangıç: 13 Kasım 2026.

Jev bağlantısı @fahrettin2001-cloud'da; bu görev onunla çakışmayan, Jev geldiğinde onu daha güvenli çalıştırmaya ve ölçmeye yarayan işleri kapsar. Her alt iş ayrı PR'dır.

| # | İş | Neden | Durum |
|---|---|---|---|
| 5.1 | Oynaklığa göre pozisyon büyüklüğü | Az emekle riski azaltır | İncelemede (bu PR) |
| 5.2 | Karar günlüğü ve güven kalibrasyonu | "Jev %70 emin dediğinde %70 haklı mı?" sorusunu cevaplar | Bekliyor |
| 5.3 | Canlı sanal işlem | Büyük modellerin geçmişi "bilmesi" sorununu ve gerçek koşulları ancak bu sınar; ekip bilgisayarında çalışacak | Bekliyor |
| 5.4 | Haber duygu analizi | Projenin asıl fikri; Jev'e ek girdi. Haberler talimat değil veridir | Bekliyor |

## 5.1 Oynaklığa göre pozisyon büyüklüğü

`jev/sizing.py` → `VolatilityTargetSizer`. Piyasa sakinken büyük, çalkantılıyken küçük pozisyon:

```
oran = hedef_günlük_oynaklık / gerçekleşen_günlük_oynaklık   (0 ile max_fraction arasına kırpılır)
gerçekleşen = son `window` barın log getirilerinin std'si × √(günlük bar sayısı)
alış tutarı = min(toplam varlık × oran, nakit)
```

Geçmiş yetersizse oran bilinmez ve alış yapılmaz. `SmaCross(..., sizer=...)` ile ya da komut satırında:

```bash
python -m jev.backtest --prices ... --fast 24 --slow 96 --vol-target 0.01 --vol-window 72 --bars-per-day 24
```

`--fraction` bu durumda üst sınır (`max_fraction`) olarak kullanılır. Risk limitleri ayrıca ve her durumda uygulanır.

### Gerçek veride sonuç (BTCUSDT 1s, Ağu–Eki 2026, SMA 24/96, gerçek kurallar, kayma 5 bps)

Bu dönemde BTC'nin 72 saatlik günlük oynaklığı %0,70 – %4,27 arasında, medyanı %1,62 idi. Bu yüzden %2 ve üstü hedefler çoğu zaman %95 üst sınırına takılıp sabit oranla aynı sonucu verdi.

| Hedef günlük oynaklık | Getiri | En büyük düşüş |
|---|---|---|
| Yok (sabit %95) | +8,83% | %13,79 |
| %1,75 | +9,06% | %13,77 |
| %1,5 | +9,42% | %13,50 |
| %1,25 | +9,86% | %12,58 |
| %1 | +11,88% | %10,96 |
| %0,75 | +14,11% | %9,16 |
| %0,5 | +11,50% | %6,63 |

Sentetik veride (farklı rejimler): sabit +29,00% / düşüş %30,36; hedef %2 → +21,69% / %15,05; hedef %1 → +11,03% / %7,86.

**Yorum:** Hedef düştükçe en büyük düşüş her iki veri setinde de düzenli olarak azaldı — beklenen ve güvenilir etki bu. Getiri ise hedefe göre düzenli değişmedi (gerçek veride inip çıktı, sentetikte azaldı). Tek dönemde en iyi görünen hedefi seçmek ezber (overfitting) olur; hedef, kabul edilebilir düşüşe göre seçilmeli. Ekipçe seçilen "temkinli" risk paketiyle birlikte günlük %1 civarı makul bir başlangıç önerisidir.

### Sınırlar

- Oynaklık geçmişe bakar; ani şoklarda gecikmeli tepki verir.
- Yalnızca giriş büyüklüğünü ayarlar; açık pozisyonu oynaklık arttıkça küçültmez (yeniden dengeleme yok).
- Tek sembol için hesaplanır; semboller arası bağıntı hesaba katılmaz.
