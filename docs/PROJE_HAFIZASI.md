# Proje hafızası ve ekip rehberi

Durum: İlk taslak — 13 Kasım 2026. Bu dosya Obsidian'da açılabilen düz Markdown biçimindedir. Her ajan başlamadan önce güncel README.md ve GOREVLER.md dosyalarını, açık çalışmaları ve kendi göreviyle ilgili bu notu okur.

## Proje özeti

Hedef, kripto piyasası verileri ve haberlerini değerlendiren; Jev, güçlü bir model ve Hermes Agent kullanılması planlanan bir sistemdir. İleride bağımsız risk denetimi sonrasında Binance üzerinde gerçek işlemler hedeflenir. Kârlılık garanti edilmez.

İlk aşama, dış servislerden bağımsız sanal işlemler: Python, Decimal, SQLite ve testler için ekipçe planlama yapılmıştır. Hangi uygulama kodunun tamamlandığı güncel depo ve açık değişikliklerden kontrol edilir. Borsa olarak Binance Global seçildi (13 Kasım 2026, `docs/kararlar/2026-11-13-binance-global.md`); onaylanmış risk limitleri henüz seçilmedi. Haber keşfi için CryptoPanic, borsaya özel duyurular için Binance Global başlangıç adayıdır; canlı bağlantı kurulmadı. Ayrıntılar: `docs/HABER-KAYNAKLARI.md`.

## Son çalışma durumu — 13 Kasım 2026, sabah

- Ana dalda çevrimdışı sanal portföy, SQLite kayıtları, örnek risk kontrolleri ve terminal arayüzü bulunuyor. Binance, Jev, Hermes veya canlı haber bağlantısı kurulu değildir.
- Yedekleme kuralları PR #9 ile ana dala alındı. Haber kaynakları ve geliştirme sınırları `docs/HABER-KAYNAKLARI.md` dosyasında.
- PR #3 açık ve çakışmalı; ana daldaki SQLite yaklaşımıyla önemli ölçüde örtüşüyor. İnceleme yapılmadan birleştirilmemeli; kapatma kararı verilmedi.
- Depo şu anda herkese açıktır. Proje sahibinin bilgisayarındaki yerel yedekleme betiğinde, depo açıkken veya görünürlük doğrulanamadığında gönderimi durduran bir kontrol var. Kontrol sahte cevapla ayrı ortamda denendi; gerçek zamanlanmış çalışma doğrulanmadı. GitHub'daki betik kopyası bu güncellemeyi henüz içermez.
- Saat 23.00 görevi oluşturuldu; ilk elle yedek başarılıydı. Depo açık kaldığı sürece otomatik gönderim durdurulacak şekilde tasarlandı; 23.00'te başarılı bir GitHub yedeği beklenmemeli. Kaçırılmış görev ve yeniden deneme davranışı henüz doğrulanmadı.
- Türkçe dosya adı okumasına yerel düzeltme yapıldı ve ayrı Git denemesi başarılı oldu; uçtan uca otomatik test yok. Gönderim hatasından sonra yeniden deneme düzeltmesi taslakta ve teste ihtiyacı var.
- SQLite için ayrı şifreli yedek kurulmadı. Proje sahibinin yerel Obsidian kopyası güncel ana dalın gerisinde ve yerel değişiklikleri var; bunlar korunarak eşitleme yapılmalı.
- Obsidian Copilot içinde Codex bağlantısı kullanılarak not okuma denendi. Sohbetlerin GitHub'a otomatik veya güvenli şekilde aktarılması kurulmuş değildir.
- Sıradaki işler: ekip arkadaşlarının haber rehberini okuması; yerel dosyaları koruyarak eşitlemenin planlanması; yedekleme betiğinin güvenli koşullarda uçtan uca testi ve şifreli SQLite yedek planı. Sayısal risk limitleri, Binance Global/TR ve haber sağlayıcısının canlı kullanımı ekipçe netleştirilecek.

## Son çalışma durumu — 13 Kasım 2026, akşam (@demirfahrieren-png)

- Görev 1 (sanal işlem çekirdeği) Tamamlandı olarak işaretlendi; ana dalda 60 test yeniden çalıştırıldı ve geçti.
- PR #10 incelendi (yorum, onay değil): dalda 67 test geçiyor, ancak `SQLitePortfolio.risk` property setter'ı sürüm kontrolü olmadan politikayı değiştirebiliyor; limitli hesapta `account.risk = RiskLimits()` sonrası izin listesi dışı ve limit üstü işlem kabul edildi (denemeyle doğrulandı). CLI etkilenmiyor. Ayrıntı ve öneri PR #10 incelemesinde. PR #11 bu dalın üzerine kurulu olduğu için düzeltmeden etkilenebilir.
- GOREVLER.md'deki terminal arayüzü notu düzeltildi: PR #8 ana dala birleşmiş.
- Görev 4 ana dala birleşti (PR #15). 13 Kasım akşamı ilk gerçek veri backtest'i: Binance Global BTCUSDT 1s, Ağu–Eki 2026, SHA-256 doğrulamalı; SMA 24/96 +8,83% (düşüş %13,79), al-tut +21,93%. Tek dönem ve tek parametre; strateji hakkında genel sonuç değil. Bulut ve masaüstü çalışma ortamlarında ağ kapalı; veri Claude masaüstü tarayıcısıyla alındı. `data/exchange_info_sample.json` artık gerçek exchangeInfo.
- PR #14 ve #10 ana dala birleşti (risk politikası sürüm denetimi; ana dalda 156 test). #11 hedefi `main` yapıldı; birleşmeden önce günlük zarar sınırının göç etmiş hesaplarda kalıcı kilit sorunu düzeltilmeli. #11 birleşince Görev 4 backtest motoru `daily_loss` / `market_prices` geçecek şekilde güncellenmeli.

## İnceleme devri — 13 Kasım 2026

- [PR #14](https://github.com/fahrettin2001-cloud/jev-crypto-trading-system/pull/14), PR #10 dalına birleştirildi; PR #10 da ana dala alındı. Kalıcı risk politikası sürüm kontrolü düzeltmesi ana daldadır. Sürüm karşılaştırması eşzamanlı değişikliklerin çakışmasını önler; yetkilendirme mekanizması değildir.
- PR #11'in hedefi ana daldır; güncel ana dalla çakışma çözümü ve entegrasyon testi gerekir. [PR #16](https://github.com/fahrettin2001-cloud/jev-crypto-trading-system/pull/16) risk sürümüne uyum ve Windows'ta geçici yedek veritabanı bağlantılarının kapatılmasını önerir. Bağımsız inceleme ve testler tamamlanmadan üst PR'ları birleştirmeyin.
- Yerelde PR #14 tek başına 68 testi geçti; PR #14 ile PR #16 bir arada denendiğinde Windows üzerinde 81 test geçti. PR #16'daki ilgili 8 test ayrıca geçti. Bunlar yerel sonuçlardır; GitHub kontrolleri ve PR'ların güncel dallara entegrasyonu ayrıca doğrulanmalı.
- Sıra: PR #16'yı PR #11 dalında incele; PR #11'in güncel ana dalla çakışmasını çöz ve tüm testleri yeniden çalıştır. Demir'in incelemesinde ana dal, PR #10 ve #14 birlikte 156 test geçtiği bildirildi. PR #3'e dokunulmadı.
- PR #11'in önerdiği yedekte geçici SQLite kopyaları şifresizdir ve silinmeleri güvenli silme garantisi vermez. Windows'ta `0o600` tek başına kullanıcıya özel ACL garantisi değildir; gerçek hassas veriler öncesi ayrıca çözüm ve hata yolu testleri gerekir. Şifreli SQLite yedeği canlı kullanım için kurulmuş veya doğrulanmış sayılmamalı.

## Nasıl birlikte çalışılır?

1. GOREVLER.md dosyasında sorumluları kontrol edin; başlamadan görevinizi işaretleyin.
2. Ortak veri modeli ve SQLite işlem sınırlarını, çekirdek ve kayıt görevlerini alan kişiler aralarında kararlaştırsın.
3. Yeni iş için güncel ana daldan ayrı dal açın; ilgili değişiklikleri ve testleri paylaşın.
4. Durum, alınan kararlar ve açık sorular için aşağıdaki şablonları kullanın.
5. Birleştirme yetkisi olan ekip üyeleri kendi değişikliklerini birleştirebilir; özellikle riskli hesaplamalarda ekip incelemesi önerilir.

## Her çalışma sonunda GitHub ve hafızayı güncelleme

Bu projede çalışan her ajan, yetkisi ve kullandığı ortamın araçları izin verdiğinde aşağıdaki adımları uygular:

1. Güncel ana dalı, kendi dalını ve devam eden işleri kontrol edin; başkalarının değişikliklerini koruyun.
2. Yapılan işle ilgili gerekli kodu, testleri ve kısa açıklamayı güncelleyin. Anlamlı proje yenilikleri için bu dosyanın güncel durumunu ve ilgili görevleri `GOREVLER.md` içinde güncelleyin; tarih, neyin değiştiği, test sonucu, açık işler ve ilgili dal/PR/commit bağlantısını belirtin.
3. Gerçekleşmiş, test edilmiş, taslak ve sadece önerilmiş işleri birbirinden ayırın; henüz birleşmemiş işi ana dalda tamamlanmış göstermeyin.
4. Değişiklikleri gözden geçirip görev için ayrı dalda commit ve GitHub'a push edin; ekip incelemesi için PR açın veya mevcut PR'ı güncelleyin. Birleştirme için görevde verilen talimatları ve depo kurallarını izleyin; açıkça yasaklanan birleştirme veya kapatma işlemi yapmayın.
5. GitHub'da commit veya PR'ın görünür olduğunu doğrulayın ve sonucu ekip üyesine aktarın. Erişim, kimlik doğrulama, test veya çatışma engel olursa bunu açıklayın; gönderilmemiş değişiklikleri gönderilmiş gibi raporlamayın. Zorla push yapmayın.
6. GitHub deposunun güncel görünürlüğünü kontrol edin: şu anda herkese açıktır. Anahtar, parola, kişisel/hassas veri, ham veritabanı ve özel sohbetleri yayımlamayın. İlgili dosyaları seçerek ekleyin; tüm klasörü körlemesine commit etmeyin.

Bu kurallar bir zamanlayıcı veya otomatik senkronizasyon oluşturmaz. Her ajan yalnızca yetkilendirildiği ve erişebildiği ortamda işlem yapabilir; yerel değişiklikler GitHub'a gönderilene kadar diğer ajanlar tarafından görülemez.

## Obsidian ve token kullanımı

Bu dosya ve depodaki diğer Markdown dosyaları bir proje klasörü olarak Obsidian'da açılabilecek şekilde tutulur. Herkesin dosyaları Git aracılığıyla nasıl güncelleyeceği ayrıca kurulmalı; bu not kendiliğinden senkronizasyon sağlamaz. Mevcut kişisel kasayı otomatik olarak paylaşmayın.

Ajan tüm geçmiş yerine önce kısa özeti, ardından ilgili görev ve karar notlarını okuyabilir. Modele gönderilen içerik yine token kullanır; sadece ilgili bölümlerin alınması tüketimi azaltabilir. İşlem kayıtları ve canlı veri Markdown notları yerine uygun veritabanında tutulur.

## Karar kaydı şablonu

- Tarih ve konu:
- Karar:
- Gerekçe ve değerlendirilen alternatifler:
- Etkilenen dosyalar / görevler:
- Açık sorular ve takip edecek kişi:

## Görev devri şablonu

- Görev ve sorumlu:
- Yapılanlar:
- Dosyalar / dal / pull request:
- Çalıştırılan testler ve sonucu:
- Eksik işler / engeller:
- Sonraki adım:

## Yedekleme ve kurtarma planı

Proje sahibinin Windows bilgisayarında yalnızca `notlar/paylasilan` Markdown notları için saat 23.00'e zamanlanmış bir GitHub yedekleme görevi oluşturuldu. 13 Kasım 2026'da elle başlatılan ilk gönderim doğrulandı; zamanında ve kaçırıldıktan sonra otomatik çalışma henüz test edilmedi. Tam kasa eşitlemesi kurulmuş değildir. SQLite verileri için ayrı şifreli yedek henüz kurulmadı.

Diğer kod ve notların yedekleme düzeni, veritabanı yedek sıklığı, saklama süresi, uyarı yöntemi ve anahtarların güvenli saklanması ekipçe belirlenecek. Günlük yedek son yedekten sonraki değişiklikleri korumayabilir. Yedekler belirli aralıklarla izole bir ortamda geri yüklenerek doğrulanmalı.

Kurtarma hedefi: (1) depoyu güvenilir kaynaktan geri al, (2) şifreli veritabanı yedeğini izole ortamda geri yükle, (3) gizli anahtarları güvenli yoldan yeniden sağla, (4) kayıtları kontrol et ve ileride gerçek hesap kullanılırsa borsa emir ve varlıklarıyla karşılaştır, (5) canlı işlem öncesi insan değerlendirmesi yap.

Şifre, API anahtarı, doğrulama kodu, gizli ortam değişkeni, gerçek hesap bilgisi ve ham hassas kayıtlar GitHub veya ortak notlara konulmaz.

## Entegrasyon planı — uygulanmadı

- Piyasa: Binance Global / TR seçimi ve önce yalnızca okunabilir veri kaynağı.
- Jev: yapılandırılmış değerlendirme; modelin puanı işlem başarısı garantisi değildir.
- Güçlü model / Hermes: aday ve haber değerlendirmesi; dış içerik talimat değil veridir.
- Risk motoru: ajandan bağımsız kontroller; başarısız veya eski veri durumunda yeni işlem açma.
- Ödül: maliyet ve riskle birlikte performans kaydı; bu kayıt Jev'i kendiliğinden eğitmez.
- Hostinger: sonraki aşama; bu taslak sunucuya dağıtım yapmaz.
