# Trend stratejisi ve sinir ağı filtresi — 16 Kasım 2026

Çevrimdışı araştırma; Jev API, borsa emri, Hostinger veya canlı/sanal bot bağlantısı yoktur.

## Soru ve yöntem

Ekibin `TrendRules` dört kuralı kullanılarak BTC ve ETH için hedef pozisyon
hesaplandı. Sinir ağının, 20 gün sonra kapanışın yükseleceği olasılığı 0,5'in
altındaysa ilgili coinin hedefi sıfırlanır. Eşik bu çalışma için sabittir;
önceki araştırma sonuçları zaten görüldüğünden önceden kayıtlı/bağımsız değildir.
Ağ 2020–2022 fiyatlarında eğitilmiş sabit bir sınıflandırıcıdır; ödülle öğrenme
ve otomatik ağırlık güncellemesi yoktur.

Başlangıç 500 sanal USDT, coin başına portföyün %30'u × trend ağırlığı,
hedeften coin payının %10'u kadar sapınca yeniden dengeleme, sıfır hedefte
satış, işlem tutarına %0,15 masraf uygulanır. İki strateji aynı simülatörü
kullanır. Karar önceki günlük kapanıştaki bilgiyle alınır; uygulama için o
kapanış fiyatı ertesi açılışın yaklaşık değeri olarak kullanılır. Gerçek
ertesi açılışlar ayrıca doğrulanmamıştır. En son değer kapanışta işaretlenir,
zorunlu kapanış maliyeti alınmaz; USD benzeri getiri faizsiz nakit varsayar.

Bu basitleştirilmiş deney sunucudaki 50 USDT işlem, 150 USDT pozisyon ve
200 USDT nakit sınırlarını ya da borsa miktar kurallarını taklit etmez;
sunucudaki botun sonuçlarıyla birebir karşılaştırılamaz.

Kaynak: `demirfahrieren-png/jev-canli-sonuclar`, commit
`726a3ed5591774bf8c506c4cd240efaad3220800`, günlük kapanış CSV'leri BTC SHA-256
`2ab03c193763b11455cfc6fb8248e5d6dfc0611622d92537570d3fd67659b5f4`, ETH
`f2751d61b1dd0ecbb662bdb171fbacc37b10bccb6864fb581d97a1753d21e808`.
Bu veriler ve strateji kuralları geçmişte incelenmiştir; 2024–2026 sonucu
bağımsız nihai sınav sayılmaz ve parametre keşfinden etkilenebilir.

## Sonuç: simülasyon

| Dönem | Strateji | Son sanal değer | Getiri | En büyük düşüş | İşlem | Masraf |
|---|---|---:|---:|---:|---:|---:|
| 2023 | Trend | 684,61 | +%36,92 | -%13,54 | 76 | 4,80 |
| 2023 | Trend + ağ | 675,83 | +%35,17 | -%14,21 | 86 | 9,09 |
| 2024–2026-10 | Trend | 852,12 | +%70,42 | -%20,02 | 214 | 17,23 |
| 2024–2026-10 | Trend + ağ | 825,16 | +%65,03 | -%19,84 | 265 | 36,25 |

Ağ filtresi iki dönemde de getiriyi azalttı ve maliyeti yükseltti. İkinci
dönemde en büyük düşüş yaklaşık 0,18 yüzde puan iyileşti; örnek ve seçim
sınırları sebebiyle bu farkın kalıcı bir avantaj olduğu söylenemez. Kârlar
gerçek hesap sonucu değildir ve geleceğe ilişkin güvenilir tahmin sağlamaz.

## Çalıştırma

```bash
python -m experiments.trend_neural_backtest --btc <BTCUSDT.csv> --eth <ETHUSDT.csv>
python -m unittest tests.test_team_neural tests.test_trend_neural_backtest
```

`experiments/team_neural.py` ve `experiments/market_neural.py` PR #49'daki
araştırmadan alınmıştır; #49 ile birleşme öncesinde yinelenen dosyalar uzlaştırılmalıdır.
