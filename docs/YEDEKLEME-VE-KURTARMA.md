# Yedekleme ve kurtarma planı

## Mevcut durum

GitHub'a gönderilen commit'ler, depoya alınmış proje kodunun ve notların bir kopyasını sağlar. Yerel ve henüz gönderilmemiş değişiklikler GitHub'da bulunmaz. Proje sahibinin Windows bilgisayarında yalnızca `notlar/paylasilan` içindeki Markdown dosyaları için her gün 23.00'e bir görev oluşturuldu. İlk manuel denemede GitHub'a gönderim doğrulandı; saatli çalışma ve kaçırılan görevin sonradan çalışması henüz test edilmedi. Diğer dosyalar ve SQLite bu otomasyonun kapsamı dışındadır.

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

Kurulu görev için Windows oturumu ve GitHub kimlik doğrulaması gerekir. Git çatışmalarında veya bağlantı hatalarında işlem durur; sonuçlar yerel `Jev-Yedekleme/yedekleme.log` dosyasındadır, ayrı bir bildirim kurulmamıştır. Görev, saatli çalışma, kaçırılan çalışma ve geri yükleme yönünden ayrıca test edilmelidir.

## Windows yedekleme betiklerini geri alma

`araclar/windows-yedekleme/` klasöründe proje sahibinin bilgisayarındaki iki betiğin kopyası bulunur. GitHub'daki kopyayı doğrudan çalıştırmak yerine, depoyu klonladıktan sonra iki dosyayı deponun yanındaki `Jev-Yedekleme` klasörüne kopyalayın. Betikler `jev-crypto-trading-system` adlı kardeş klasörü ve Windows için varsayılan Git yolunu kullanır. `yedekle.ps1` içindeki GitHub depo adresi ve commit kimliği proje sahibine özeldir; başka ekip üyeleri kurmadan önce kendi çalışma düzenlerine göre gözden geçirmelidir. `kur.ps1` ilk yedekleme denemesinin ardından Windows görevi oluşturmaya çalışır. Mevcut görevi değiştirmeden önce betikleri inceleyin. Bu kopyaların varlığı başka bir bilgisayarda görevin kurulduğu anlamına gelmez.
