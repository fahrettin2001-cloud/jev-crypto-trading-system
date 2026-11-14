# Görev 6: zaman sıralı veride ilk sinir ağı araştırması

Bu çalışma PR #32'deki küçük `TinyNetwork` sınıfını, PR #35'teki zaman
sıralı araştırma ve sabit lojistik karşılaştırma düzenine uygular. Eğitim
denetimlidir; ödülle öğrenme veya Jev API entegrasyonu değildir. Tamamen
çevrimdışıdır, sanal/gerçek işlem motoruna, Hostinger'a veya borsaya erişmez.

## Yöntem

- Girdiler yalnızca kapanmış mum ve önceki kapanışlardan hesaplanan iki getiri;
  amaç belirlenen sayıda mum sonraki kapanışın daha yüksek olup olmadığını ölçmek.
- Aynı veri ve örnekler temel model, sabit 0,5 ve sinir ağı için kullanılır.
  `build_splits` hedefi bölüm sınırını aşan örnekleri ayıklar.
- Ortalama ve standart sapma yalnızca eğitim bölümünden hesaplanır; sıfır
  sapmada ölçek 1 kullanılır. Doğrulama/test veri ölçeği veya model ağırlıklarını
  belirlemez. 8 nöron, 1500 eğitim adımı, grup 32, hız 0,1 ve tohumlar sabittir.
- Brier olasılık hatası ile doğruluk bildirilir. Bu ölçütler işlem maliyetini,
  kârlılığı, gecikmeyi ve gerçek yürütmeyi ölçmez. Üç mumluk hedefler örtüşür;
  örnekler bağımsız gözlem kabul edilmemelidir.

```bash
python -m experiments.market_neural --prices data/synthetic_prices.csv --symbol BTCUSDT --data-kind synthetic
python -m unittest tests.test_market_neural tests.test_market_research
```

Dosya içeriğini doğrulamak yerine kullanıcı tarafından belirtilen `--data-kind`
etiketi rapora kaydedilir; veri kaynağı ayrıca kontrol edilmelidir. Dosyanın
SHA-256 değeri çalıştırıldığı andaki yerel dosya baytlarına aittir; Git satır
sonu dönüşümleri Windows ve Linux'ta farklı değerler üretebilir.

## İlk deneme — 14 Kasım 2026

Sentetik BTCUSDT dosyası, 1 saat, 6 mum geçmiş ve 3 mum ufuk; eğitim 1287,
doğrulama 429, test 429 örnek. Test bölümünde:

| Yöntem | Doğruluk | Brier (düşük daha iyi) |
|---|---:|---:|
| Sinir ağı | %44,99 | 0,2690 |
| Lojistik temel model | %44,99 | 0,2566 |
| Sabit 0,5 olasılık | %56,18 | 0,2500 |

Bu örnekte ağ, basit sabit olasılıktan daha yüksek hata verdi. Veri sentetik;
bu sonuçlar gerçek piyasadaki veya ticaretteki başarısına dair kanıt değildir.
Bu veri ve test bölümü önceki araştırmada da incelendiği için deney geliştirme
kararlarından bağımsız, nihai dokunulmamış sınama olarak kabul edilmemelidir.
Parametreler bu sonuçları gördükten sonra iyileştirilmedi.

## Doğrulama durumu

Yerelde erişilebilen sınırlı Python 3.13 ile örnek çalıştırıldı. Eğitimden
sonraki fiyatların değiştirilmesi, eğitilen ağırlık ve eğitimden hesaplanan
ölçekleri değiştirmedi; sabit özellik, tekrarlanabilirlik ve karşılaştırılan
örnek sayıları elle kontrol edildi. Ayrı otomatik testler eklendi; bu ortamda
`unittest` ve `sqlite3` eksik olduğundan tam Python bulut ortamında çalıştırılıp
bağımsız incelenmeleri gerekir. Eski veri doğrulama kodu tüm olası sızıntıları
veya modelin eğitildiği diğer kaynakları otomatik garanti etmez.
