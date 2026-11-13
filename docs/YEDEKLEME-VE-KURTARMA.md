# Yedekleme ve kurtarma planı

## Mevcut durum

GitHub'a gönderilen commit'ler, depoya alınmış proje kodunun ve notların bir kopyasını sağlar. Yerel ve henüz gönderilmemiş değişiklikler GitHub'da bulunmaz. Her gün otomatik yedekleme henüz kurulmuş veya doğrulanmış değildir.

## Gün sonu: manuel işlem

1. Proje klasöründe `git status` ile değişiklikleri inceleyin.
2. Paylaşılacak dosyalarda sır, kişisel bilgi veya veritabanı bulunmadığını kontrol edin. `.gitignore` tek başına tüm gizli bilgileri algılamaz; daha önce takip edilen dosyaları da otomatik olarak takipten çıkarmaz.
3. Sadece paylaşılacak dosyaları ekleyip commit oluşturun ve `git push` ile gönderin.
4. Komut başarılı olduktan sonra GitHub üzerinde commit'in ve dosyaların göründüğünü kontrol edin. Gönderme reddedilirse hatayı çözmeden başarı varsaymayın.

## Yeni bilgisayarda geri dönme

1. Git ve Obsidian kurun; özel depoya erişimi olan GitHub hesabıyla giriş yapın.
2. Depoyu klonlayın: `git clone https://github.com/fahrettin2001-cloud/jev-crypto-trading-system.git`.
3. Obsidian'da mevcut klasörü kasa olarak açın. `OBSIDIAN-BASLANGIC.md` ve `docs/PROJE_HAFIZASI.md` dosyalarını okuyun.
4. Gerekli gizli bilgileri güvenli sır yöneticisinden yeniden sağlayın. GitHub deposu bunların yedeği değildir.
5. Gerekliyse ayrı korunan veritabanı yedeğini geri yükleyin; önce uygulama kapalıyken bir kopya üzerinde test edin.

## Veritabanı ve otomasyon

SQLite verileri GitHub notlarından ayrı tutulur. İleride veritabanı kullanıldığında tutarlı yedek için SQLite'ın backup API'si gibi uygun bir yöntem kullanılmalı, yedek şifrelenmiş ve erişimi sınırlandırılmış ayrı bir yerde tutulmalıdır. Geri yükleme bir kopya üzerinde düzenli olarak denenmelidir.

Günlük otomatik çalışma kurulmadan önce çalıştırılacak bilgisayarın açık olması, kimlik doğrulama, başarısızlık bildirimi, çatışmalar, gizli bilgilerin dışlanması ve geri yükleme testi kararlaştırılmalıdır. Bu dosya bir otomasyon kurmaz.
