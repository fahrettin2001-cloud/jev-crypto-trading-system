# Görev 6: zaman sıralı araştırma ortamı

Bu ilk araştırma aracı **yalnızca çevrimdışı tahmin değerlendirmesi** yapar.
İşlem, portföy, gerçek/sanal emir, Jev API çağrısı veya ödülle öğrenme içermez.
Küçük sinir ağı ve ödül örneklerinden bağımsızdır. Amaç, ileride aday modelleri
eklemeden önce veri bölme ve ölçüm kurallarını çalıştırılabilir hale getirmektir.

## Çalıştırma

```bash
python -m experiments.market_research --prices data/synthetic_prices.csv --symbol BTCUSDT
python -m unittest tests.test_market_research
```

Varsayılan örnek veriler **sentetiktir**. Başka bir yerel CSV kullanılabilir:
başlık `timestamp,symbol,close`, saat dilimli ISO zaman, pozitif sonlu fiyat;
varsayılan mum aralığı 1 saat. `--interval-seconds`, `--lookback` ve `--horizon`
değiştirilebilir. Aynı sembolde zaman sırası bozuksa, mum eksikse veya tekrar
varsa araç durur; eksik veri doldurulmaz. Girdi dosyası SHA-256 değeri raporlanır.

## Veri sızıntısı sınırları

Her tahmin kapanmış bir mumun kapanışında yapılır. Girdiler yalnızca o an ve
önceki fiyatlardan hesaplanan son bir mum ve `lookback` mumluk yüzdesel
getiridir. Hedef, `horizon` mum sonraki kapanışın şimdikinden yüksek olmasıdır;
eşitlik yükseliş değildir.

Fiyat dizisi zamana göre sırasıyla %60 eğitim, %20 doğrulama, %20 test olarak
ayrılır. Bir örneğin hedefi kendi bölümünden taşacaksa örnek **atılır**.
Doğrulama/test başlangıcında önceki kapanışların geçmiş olarak kullanılması
gerçek zamanda mevcut bilgiye dayanır. Ayarlar sabittir; model ve sabit sınıf
oranı yalnızca eğitim bölümünden hesaplanır; doğrulama/testte yeniden eğitim
yapılmaz. Birden fazla deneme yapıp en iyi test sonucunu seçmek sonuçları
geçersizleştirebilir. Bölümler arasında eğitim sürecini otomatik yenileyen bir
walk-forward deneyi burada uygulanmamıştır.

## Karşılaştırmalar ve sınırlar

Çalıştırılan model, iki özellikli sabit ayarlı **lojistik temel modeldir**;
sinir ağı veya öğrenen trade botu olduğu iddia edilmez. Aynı örnekler üzerinde
eğitimde en çok görülen sınıf, eğitimdeki yükseliş oranı ve sabit 0,5 olasılığı
da gösterilir. Sonuçlar doğruluk ve Brier puanıdır; 0,5 tahmininde eşitlik
sınıflandırması yükseliş kabul edilir. Üç saatlik ufuk gibi çakışan hedefler
birbirinden bağımsız gözlem sayılmamalıdır.

Bu ölçümler komisyon, kayma, pozisyon ve işlem yapmayı modellemez; dolayısıyla
**kâr/zarar, sağlamlık veya gerçek işlem yeterliliği sonucu değildir**. İşlem
stratejisi performansı için ayrı backtest ve canlıya dönük sanal çalışma
gerekir. Demir'in mevcut strateji sağlamlık çalışması `jev/saglamlik.py` ve
`docs/saglamlik-2026-11.md` ile koordine edilmelidir. Jev ya da başka bir
modelin çıktısı bu araca henüz verilmez.

## İlk sentetik deneme — 13 Kasım 2026

`data/synthetic_prices.csv`, BTCUSDT, 1 saatlik aralık, 6 mum geçmiş ve 3 mum
ufuk kullanıldı. Dosya SHA-256:
`d0fac78cfb185161c6529bef1cf6ec78c462758c9a61a92160fa3f41b03a0bea`.
Eğitim/doğrulama/test sırasıyla 1287/429/429 örnekti. Test bölümünde lojistik
model doğruluğu %44,99 ve Brier 0,2566; sabit 0,5 olasılığın Brier puanı 0,25
oldu. 0,5 eşitlik kuralındaki doğruluk %56,18'di. Model bu örnekte olasılık
ölçütünde basit sabit karşılaştırmayı geçmedi; bu sentetik sonuç gerçek piyasa
başarısı veya başarısızlığını göstermez.

Python 3.12.14 ile 8 özel test ve toplam 214 proje testi geçti. Eski
`tests/test_backtest_orders.py` içinde açık bırakılan iki CSV dosyası için
ResourceWarning görüldü. Testler geçmiş/gelecek ayrımı, bölüm sınırı,
tekrarlı/eksik veri, sabit model eğitimi ve tekrarlanabilir raporu kapsar.
