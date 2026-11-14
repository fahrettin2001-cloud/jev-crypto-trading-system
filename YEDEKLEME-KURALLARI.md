# Yedekleme kuralları

Bu belge, üç kişilik ekibin ve ajanlarının proje hafızasını güvenli ve anlaşılır biçimde paylaşması için hazırlanmıştır. Kurallar kendi başına yedekleme veya senkronizasyon yapmaz.

## Çalışma kararı — manuel Obsidian güncellemesi

13 Kasım 2026: Proje sahibi, saatlik/günlük otomatik Obsidian yedekleme yerine isteğe bağlı manuel güncelleme istedi. Ekip ve ajanlar kod/not değişikliklerini gözden geçirip GitHub'a commit ve push eder; inceleme gerektiren işler PR ile paylaşılır. Proje sahibi istediğinde yerel değişiklikleri koruyarak güncel GitHub içeriğini Obsidian'daki depo kopyasına alır. Git pull otomatik değildir ve yerel değişiklikler varsa çakışmalar incelenir.

Proje sahibi Windows'taki 23.00 görevini devre dışı bıraktığını bildirdi; bu ajan cihazda bağımsız doğrulama yapamadı. GitHub herkese açıksa yalnızca herkese açık olmaya uygun içerik gönderilir. GitHub kod ve notları, SQLite verilerinin şifreli yedeği değildir; bu yedek ayrıca planlanır.

## Ne paylaşılır?

- GitHub deposu, ekipçe paylaşılacak kodun ve proje notlarının ortak kaynağıdır. Depo şu anda herkese açıktır; GitHub'a gönderilen içerikler herkes tarafından görülebilir.
- Windows'taki mevcut otomatik görev yalnızca `notlar/paylasilan/` içindeki Markdown (`.md`) notlarını göndermeyi hedefler. Diğer notlar, kod, Obsidian ayarları ve veritabanları bu görevin kapsamında değildir.
- Bu kurallar dosyası depo kökündedir; mevcut otomatik görevin kapsamı dışındadır. GitHub'da da bulunması için ayrıca gözden geçirilip commit ve push edilmelidir.
- Bu klasöre yalnızca tüm ekip üyeleriyle paylaşılmaya hazır notlar konur. Değişikliklerin GitHub'a gönderildiği doğrulanana kadar bilgisayarda kalabileceği unutulmaz.

## Gizlilik

- API anahtarları, parolalar, kurtarma kodları, oturum bilgileri, gerçek hesap bilgileri ve hassas kişisel veriler paylaşım notlarına veya GitHub deposuna yazılmaz.
- SQLite dosyaları, günlükleri ve yedekleri GitHub'a gönderilmez; bunlar için ayrıca şifreli ve erişimi sınırlandırılmış bir yedekleme düzeni gerekir. Bu düzen henüz kurulmamıştır.
- `.gitignore` ve betikteki otomatik gizli bilgi kontrolleri tüm sırları yakalamaz. Paylaşılacak içeriği yazan kişi kontrol eder.

## Mevcut otomatik görev

- Proje sahibinin Windows bilgisayarında her gün yerel saatle 23.00 için bir görev oluşturulmuştur. Kaçırılan görevin bilgisayar ve kullanıcı oturumu açıldığında çalışması ayarlanmıştır; bu davranış ve saatli çalışma henüz test edilmemiştir.
- İlk elle başlatılan not gönderimi GitHub üzerinde doğrulanmıştır. Görevin çalışması bilgisayarın ve kullanıcı oturumunun açık olmasına, internet bağlantısına ve GitHub kimlik doğrulamasına bağlıdır.
- Bilgisayardaki betiğe, depo herkese açık olduğunda veya gizlilik durumu doğrulanamadığında işlemi durduran bir kontrol eklenmiştir. Bu kontrol örnek ortamda denendi; zamanlanmış görevin gerçek çalışma koşullarında henüz doğrulanmadı. GitHub'daki betik kopyası henüz bu güncellemeyi içermez.
- Sonuçlar yerelde `Jev-Yedekleme/yedekleme.log` dosyasına kaydedilir. Ayrı hata bildirimi kurulmamıştır.
- Çakışma veya hata varsa zorla gönderme yapılmaz; önce durum incelenir. Hata kaydı, başarılı bir yedek anlamına gelmez.

## Bilinen eksikler

1. Türkçe karakter içeren dosya adları için yerel betikte düzeltme yapıldı; ayrı Git denemesinde okuma başarılı oldu. Otomatik görevle uçtan uca henüz doğrulanmadı.
2. Yerel commit oluşturulduktan sonra GitHub'a gönderim başarısız olursa sonraki otomatik denemeler durabilir. Bu durumun giderilmesi ve yeniden denemenin test edilmesi gerekir.
3. SQLite için ayrı şifreli yedek ve geri yükleme testi yoktur. GitHub not yedeği veritabanının yedeği değildir.
4. Saatli çalışma, bilgisayar kapalıyken kaçırılan görevin sonradan çalışması ve GitHub'dan yeni bir bilgisayara tam geri yükleme henüz uçtan uca doğrulanmamıştır.

## Ajanlar için çalışma kuralları

1. Önce güncel `GOREVLER.md`, `docs/PROJE_HAFIZASI.md` ve ilgili görevin notlarını okuyun; bir değişikliğin hangi dalda veya PR'da olduğunu kontrol edin.
2. Yalnızca doğrulanan bilgileri kaydedin. Önerileri, belirsizlikleri ve henüz yapılmayan işleri açıkça işaretleyin.
3. Yedeklemeyi veya gerçek işlem bağlantısını, test edilmediyse çalışıyor diye raporlamayın.
4. Gönderilecek notları gözden geçirin; ekip değişiklikleriyle çakışma varsa koruyarak çözün ve zorla push yapmayın.
5. Kurtarma ve teknik ayrıntılar için `docs/YEDEKLEME-VE-KURTARMA.md` ve `docs/AJAN-HAFIZASI.md` dosyalarına bakın; çelişki varsa en güncel doğrulanmış durumu ayrıca teyit edin.

