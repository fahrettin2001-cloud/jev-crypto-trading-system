# GitHub ve Obsidian çalışma döngüsü

Durum: plan. Bu dosya senkronizasyon, Git bağlantısı veya otomatik commit kurmaz.

## Ortak kaynak

Projenin özel GitHub deposu ortak kaynak olarak kullanılacak. Obsidian'daki Markdown notları daha sonra bu depodaki belirli bir klasörle eşleştirilmeli. Bulut oturumu bu bilgisayardaki klasöre kendiliğinden erişemez; paylaşım GitHub veya ayrıca kurulacak güvenilir bir eşitleme üzerinden gerçekleşir.

## Çalışma sırası

1. Yerelde değişiklik yapmadan önce GitHub'ın güncel durumunu al; kaydedilmemiş yerel değişiklikleri koru.
2. Proje değişikliklerini, ilgili kodu ve kararları incele. Yalnızca doğrulanan bilgileri notlara ekle; belirsiz veya uygulanmamış konuları açıkça işaretle.
3. Obsidian'da notları oku ve düzenle. Copilot'un notları GitHub'a göndermesi için kullandığı araçların Git yazma ve GitHub kimlik doğrulama desteği ayrıca doğrulanmalıdır.
4. Değişiklikleri gözden geçir; gizli anahtarlar, şifreler, .env dosyaları, kişisel notlar ve veritabanlarını commite ekleme.
5. Yetkili GitHub hesabıyla değişiklikleri commitle ve push et. Çakışma olursa iki tarafın değişikliklerini koruyarak çöz; zorla push yapma.
6. Diğer ekip üyeleri ve ajanları güncel depoyu alıp ilgili Markdown notlarını okuyabilir. Bu, ajanların notları otomatik olarak hatırladığını garanti etmez.

## Henüz tamamlanmamış kararlar

- Bu yerel kasa ile depodaki doküman klasörünün tam eşleşmesi ve ilk birleştirme yöntemi.
- Yerel Git/GitHub oturumunun yeniden doğrulanması.
- Copilot'un güvenilir Git araçlarına gerçekten erişimi ve yazma izinleri.
- Günlük otomatik yedekleme, hata bildirimi ve geri yükleme testi.

GitHub kod ve uygun notların yedeği olabilir. SQLite ve diğer operasyon verileri için ayrıca şifreli, test edilmiş yedek gereklidir. Günlük yedek, son yedekten sonraki değişikliklerin kaybedilmesini önlemez.
