# Gelecekteki entegrasyon taslağı

Durum: Tasarım önerisi. Bu belge borsa bağlantısı, ajan, haber servisi, eğitim veya gerçek işlem kurmaz. Mevcut uygulama için önce güncel README ve kod esas alınır.

## İş akışı

1. **Veri:** İleride piyasa verisi ve haberler kaynak, zaman ve geçerlilik bilgisiyle alınır. İlk denemeler örnek verilerle ve çevrimdışı yapılır.
2. **Hızlı değerlendirme:** Jev için düşünülen bileşen adayları değerlendirip gerekçeli, yapılandırılmış öneriler üretir. Uygunluk ve hız gerçek entegrasyonda ölçülmelidir.
3. **İkinci değerlendirme:** Güçlü model / Hermes, ihtiyaç olduğunda bağlamı ve haberleri değerlendirir. Haber veya diğer dış içerikler komut değil veridir.
4. **Bağımsız risk kontrolü:** Öneri kurallara göre değerlendirilir; eksik veri, eski fiyat veya hata varsa yeni işlem reddedilir. Limitler ekipçe belirlenmedikçe örnek kabul edilir.
5. **Sanal işlem:** Onaylanan öneri önce simülasyona gider. Sonuç, maliyet ve gerekçesi kayıt altına alınır.
6. **Değerlendirme:** Performans, ücretler ve riskle birlikte ölçülür; sonuçlar yatırım başarısı garantisi vermez.

## Bileşenler arasında önerilen bilgiler

- Piyasa gözlemi: kaynak, işlem çifti, fiyat, gözlem zamanı ve geçerlilik.
- Haber: kaynak, yayın zamanı, bağlantı ve kısa özet.
- Öneri: varlık, yön, gerekçe, kullanılan veri zamanı ve değerlendirme kimliği.
- Risk sonucu: kabul veya ret, nedenler, kullanılan limit sürümü.
- İşlem kaydı: karar kimliği, sanal emir, uygulanan fiyat, ücret ve sonuç.

Bunlar henüz uygulanmış arayüzler değildir; ekip mevcut veri modelleriyle uyumlarını değerlendirmelidir.

## Ödül sinyali

Kârı tek başına “mutluluk” sinyali saymak, aşırı risk almaya ve kısa vadeli kâra odaklanmaya yol açabilir. Önce ücretleri, kaybı ve alınan riski de içeren ölçümler kaydedilmeli; eğitim veya otomatik strateji değişikliği ayrı tasarlanıp test edilmelidir. Sinyal eklemek bir modelin kendiliğinden öğrendiği anlamına gelmez.

## Açık kararlar

- Binance Global veya Binance TR ve kullanılacak piyasa veri kaynağı.
- Jev ve güçlü modelin erişimi, gecikmesi, maliyeti ve gerçekten hangi görevlerde kullanılacağı.
- Haber kaynakları, veri güncelliği ve değerlendirme sıklığı.
- Test bütçesi, komisyon, risk limitleri ve performans ölçütleri.
- SQLite yedeği için şifreleme, ayrı depolama ve geri yükleme testi.
- Hostinger dağıtımı ve gerçek emirler, daha sonra ayrı karar ve test gerektirir.
