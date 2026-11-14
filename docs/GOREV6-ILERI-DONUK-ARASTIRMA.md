# Görev 6: ileriye dönük pencere araştırması

Bu araç geçmiş fiyat dizisi üzerinde zaman ilerledikçe modeli **ayrı ayrı
yeniden eğitip** takip eden pencerede değerlendiren çevrimdışı bir araştırmadır.
Canlı/gölge bot, Jev, ödülle öğrenme, emir veya kârlılık hesabı içermez.

## Yöntem ve sınırlar

- Dizinin ilk %40'ı başlangıç eğitim alanıdır. Sonraki yaklaşık %10'luk dört
  pencerede her seferinde sinir ağı ve lojistik temel model yeniden eğitilir;
  ölçek yalnızca o pencereye kadar olan eğitim verisinden hesaplanır.
- Eğitim örneğinin hedefi değerlendirme döneminin ilk zamanından **önce**
  bitmelidir. Değerlendirme hedefi kendi penceresinin dışına çıkamaz; sınırı
  aşan örnekler atılır. Önceki pencerelerde tamamlanan hedefler, daha sonraki
  pencerelerin eğitiminde kullanılabilir.
- Son %20 bu araştırma yürütülürken eğitim ve değerlendirme örneği olarak
  kullanılmaz; kaynak dosyanın bütünlüğü doğrulanır ve tamamı için SHA-256
  kaydedilir. Ancak mevcut sentetik dosyanın bu dönemi önceki PR #35 ve #37'de
  incelendiğinden **bağımsız nihai test olduğu iddia edilmez**.
- Her pencere aynı örneklerde ağ, lojistik model, eğitimdeki yükseliş oranı ve
  sabit 0,5 olasılığıyla Brier/doğruluk ölçer. Ufuklar örtüştüğünden örnekler
  bağımsız kabul edilmez. Gerçek işlem maliyeti veya getiri hesaplanmaz.
- Pencere içindeki model örnek sayıları ve metrikler doğrulanır; toplu skorlar
  pencere örnek sayılarıyla ağırlıklandırılır. Model ayarları rapora yazılır.

```bash
python -m experiments.walk_forward --prices data/synthetic_prices.csv --symbol BTCUSDT --data-kind synthetic
python -m unittest tests.test_walk_forward tests.test_market_neural tests.test_market_research
```

Veri biçimi ve zamana ilişkin kontroller `docs/GOREV6-PIYASA-ARASTIRMA.md`
ile aynıdır. `--data-kind` yalnızca kullanıcı beyanıdır. Kaynakların güvenilirliği,
yayın zamanı ve modelin başka kaynaklardan geçmiş bilgisi bu araçla kanıtlanmaz.
Dosya özeti işletim sistemi satır sonlarına göre farklılık gösterebilir.

## İlk sentetik sonuç — 14 Kasım 2026

BTCUSDT için 1 saatlik sentetik veri, 6 mum geçmiş, 3 mum ufuk ve her pencerede
213 değerlendirme örneği kullanıldı. Son 432 mum ayrıldı ve değerlendirilmedi.

| Pencere | Ağ Brier | Lojistik Brier | Sabit 0,5 Brier |
|---|---:|---:|---:|
| 1 | 0,2560 | 0,2511 | 0,2500 |
| 2 | 0,2402 | 0,2398 | 0,2500 |
| 3 | 0,2710 | 0,2546 | 0,2500 |
| 4 | 0,2636 | 0,2573 | 0,2500 |

Burada düşük Brier daha iyidir. Ağ, 4 pencerenin 1'inde sabit 0,5 tabanından
iyi; 4'ünde lojistik modelden daha kötü sonuç verdi. Bu **sentetik veri** gerçek
piyasa başarısı, kârlılık veya riskin düşük olduğu anlamına gelmez.

Dört pencerenin 852 örnekli ağırlıklı özetinde Brier: ağ 0,2577, lojistik
0,2507, eğitimdeki yükseliş oranı 0,2504 ve sabit 0,5 için 0,2500. Bu
örneklerin hedefleri örtüşebilir ve bağımsız gözlemler olarak yorumlanamaz.

## Doğrulama

Sınırlı yerel Python 3.13 ile pencere sırası, hedeflerin sınırlarda ayıklanması,
ayrılan dönemin değiştirilmesinin araştırma örneklerine etkisizliği, aynı örnek
sayıları ve geçersiz veri elle denendi. GitHub Actions üzerinde `9cc184e` sürümü Python 3.10, 3.12 ve 3.13 ile
test edildi ve tüm işler başarılı tamamlandı. Python 3.12 Linux çalışmasında
261 test çalıştırıldı, 1 Windows'a özel test atlandı; aynı test Windows'taki
ayrı çalışmada geçti. Yeni dört pencere testi de başarılıydı. Bu sonuç yalnızca
kod doğrulamasıdır; modelin gerçek piyasa başarısını göstermez.

Karşılaştırma güvencesi değişiklikleri yerelde elle kontrol edildi; yeni
testlerin ve tüm testlerin GitHub Actions sonucu ayrıca doğrulanmalıdır.
