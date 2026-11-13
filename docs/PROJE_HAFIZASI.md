# Proje hafızası ve ekip rehberi

Durum: İlk taslak — 13 Kasım 2026. Bu dosya Obsidian'da açılabilen düz Markdown biçimindedir. Her ajan başlamadan önce güncel README.md ve GOREVLER.md dosyalarını, açık çalışmaları ve kendi göreviyle ilgili bu notu okur.

## Proje özeti

Hedef, kripto piyasası verileri ve haberlerini değerlendiren; Jev, güçlü bir model ve Hermes Agent kullanılması planlanan bir sistemdir. İleride bağımsız risk denetimi sonrasında Binance üzerinde gerçek işlemler hedeflenir. Kârlılık garanti edilmez.

İlk aşama, dış servislerden bağımsız sanal işlemler: Python, Decimal, SQLite ve testler için ekipçe planlama yapılmıştır. Hangi uygulama kodunun tamamlandığı güncel depo ve açık değişikliklerden kontrol edilir. Binance çeşidi, risk limitleri ve haber kaynakları henüz seçilmedi.

## Nasıl birlikte çalışılır?

1. GOREVLER.md dosyasında sorumluları kontrol edin; başlamadan görevinizi işaretleyin.
2. Ortak veri modeli ve SQLite işlem sınırlarını, çekirdek ve kayıt görevlerini alan kişiler aralarında kararlaştırsın.
3. Yeni iş için güncel ana daldan ayrı dal açın; ilgili değişiklikleri ve testleri paylaşın.
4. Durum, alınan kararlar ve açık sorular için aşağıdaki şablonları kullanın.
5. Birleştirme yetkisi olan ekip üyeleri kendi değişikliklerini birleştirebilir; özellikle riskli hesaplamalarda ekip incelemesi önerilir.

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

Henüz otomatik yedekleme veya Obsidian eşitlemesi kurulmadı. Hedef: kodu ve gizli bilgi içermeyen proje notlarını özel GitHub deposunda sürümlemek; uygulama veritabanı yedeklerini ayrı, şifreli bir depolama alanında saklamak.

Günlük kod/not yedeği ve daha sık veritabanı yedeği seçenekleri, saklama süresi, uyarı yöntemi ve anahtarların güvenli saklanması ekipçe belirlenecek. Günlük yedek son yedekten sonraki değişiklikleri korumayabilir. Yedekler belirli aralıklarla izole bir ortamda geri yüklenerek doğrulanmalı.

Kurtarma hedefi: (1) depoyu güvenilir kaynaktan geri al, (2) şifreli veritabanı yedeğini izole ortamda geri yükle, (3) gizli anahtarları güvenli yoldan yeniden sağla, (4) kayıtları kontrol et ve ileride gerçek hesap kullanılırsa borsa emir ve varlıklarıyla karşılaştır, (5) canlı işlem öncesi insan değerlendirmesi yap.

Şifre, API anahtarı, doğrulama kodu, gizli ortam değişkeni, gerçek hesap bilgisi ve ham hassas kayıtlar GitHub veya ortak notlara konulmaz.

## Entegrasyon planı — uygulanmadı

- Piyasa: Binance Global / TR seçimi ve önce yalnızca okunabilir veri kaynağı.
- Jev: yapılandırılmış değerlendirme; modelin puanı işlem başarısı garantisi değildir.
- Güçlü model / Hermes: aday ve haber değerlendirmesi; dış içerik talimat değil veridir.
- Risk motoru: ajandan bağımsız kontroller; başarısız veya eski veri durumunda yeni işlem açma.
- Ödül: maliyet ve riskle birlikte performans kaydı; bu kayıt Jev'i kendiliğinden eğitmez.
- Hostinger: sonraki aşama; bu taslak sunucuya dağıtım yapmaz.
