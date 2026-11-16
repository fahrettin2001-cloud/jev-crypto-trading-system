# Ekip sinyalleri ve küçük sinir ağı — 16 Kasım 2026

Çevrimdışı araştırma: PR #38'deki küçük ağ, ekibin sinyal laboratuvarındaki
günlük fiyat verileri ve iki teknik gösterge ile karşılaştırıldı. Emir, Jev
çağrısı, ödülle öğrenme ve canlı/sanal bota entegrasyon yoktur.

## Yöntem

- Kaynak: `demirfahrieren-png/jev-canli-sonuclar`, commit
  `726a3ed5591774bf8c506c4cd240efaad3220800`, `veri/genis/kripto/` BTCUSDT
  ve ETHUSDT günlük kapanışları. Dönüşüm dosyalarının SHA-256 değerleri:
  BTC `2ab03c193763b11455cfc6fb8248e5d6dfc0611622d92537570d3fd67659b5f4`,
  ETH `f2751d61b1dd0ecbb662bdb171fbacc37b10bccb6864fb581d97a1753d21e808`.
- Eğitim 2020–2022; doğrulama 2023; değerlendirme 2024–31 Ekim 2026.
  Hedef 20 gün sonraki kapanışın karar günü kapanışından yüksek olmasıdır;
  hedef başka bölüme taşarsa örnek atılır. Kararda geçmiş fiyatlar kullanılır.
- Aynı örneklerde iki ayrı giriş denenir: eski yöntem (1 ve 6 günlük getiri),
  ekibin incelediği özellikler (30 günlük getiri ve 50 günlük ortalamaya uzaklık).
  Ayrı eğitimli ağlar, aynı girdilerle lojistik model, eğitimdeki yükseliş oranı
  ve sabit 0,5 olasılık karşılaştırılır. Ölçekler yalnızca eğitimden hesaplanır.
- Bu dönemler ekibin daha önce incelediği verilerdir; bağımsız nihai sınav
  değildir. Özellikler ve deney o çalışmaların sonuçları görüldükten sonra
  seçildi. 20 günlük hedefler örtüşür; örnekler bağımsız sayılmaz.

## Sonuç

Düşük Brier daha iyidir. Değerlendirme bölümünde her satırda 1.015 örnek var.

| Coin | Ağ girdileri | Ağ Brier | Lojistik Brier | Eğitim oranı | Sabit 0,5 |
|---|---|---:|---:|---:|---:|
| BTC | Eski | 0,252632 | 0,249900 | 0,250331 | 0,250000 |
| BTC | Ekip sinyalleri | 0,250579 | 0,249065 | 0,250331 | 0,250000 |
| ETH | Eski | 0,259469 | 0,255848 | 0,259092 | 0,250000 |
| ETH | Ekip sinyalleri | 0,260088 | 0,254389 | 0,259092 | 0,250000 |

BTC ağı ekip girdileriyle iyileşti ama sabit 0,5'in arkasında kaldı; ETH ağı
bu girdilerle biraz kötüleşti. Her iki coinde lojistik model ağdan daha iyi.
Brier tahmin kalitesini ölçer; bu sonuç işlem getirisi veya kârlılık ölçmez.
Bu, trend stratejisiyle birleştirilmiş işlem backtesti değildir.

## Çalıştırma

```bash
python -m experiments.team_neural --prices <BTCUSDT.csv> --symbol BTCUSDT
python -m experiments.team_neural --prices <ETHUSDT.csv> --symbol ETHUSDT
python -m unittest tests.test_team_neural
```

Veri dış kaynaklıdır ve repoya dahil değildir; kaynak commit ve özetler yukarıda.
