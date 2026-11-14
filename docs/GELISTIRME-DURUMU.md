# Geliştirme durumu — 13 Kasım 2026

PR #10 ve #14 ana dalda; #16, PR #11 dalına birleşmiştir. Bu dal güncel ana dalla
birleştirilip entegrasyon testinden geçirildi; PR #11, 14 Kasım 2026 tarihinde 34b1e2e commit’iyle ana dala alındı.

## Hazırlanan ve yerelde doğrulananlar

- AES-256-GCM şifreli SQLite yedeği, backup API ile WAL dahil tutarlı kopya,
  bütünlük/anahtar doğrulaması ve mevcut hesabı ezmeyen geri yükleme.
- Günlük gerçekleşen kayıp limiti: UTC yürütme günündeki negatif gerçekleşen
  sonuçların mutlak toplamı. Kârlar kaybı silmez. Eşik dolunca yeni alış durur;
  satış sürer. Açık pozisyonun gerçekleşmemiş zararı bu limit değildir.
- Eski `executed_at` alanı boş kayıtlarda kayıtlı `timestamp` UTC gününe çevrilir;
  yalnızca ilgili günün kaybı sayılır. Önceki günlerin zararı hesabı kalıcı kilitlemez.
  İşlem için kullanıcı tarih vermesi yürütme gününü değiştirmez. Güvenilir saat
  sağlayıcı test/simülasyon içindir; dış içerik saat sağlayıcı olamaz.
- Tüm pozisyonlar için değer sınırı: `max_total_position_notional`. Bu limit
  kullanılırken `max_price_age_seconds` de zorunlu. Diğer sembollerin zamanlı
  değerleme fiyatları eksik/eskiyse alış durur; tam sınır kabul edilir.
- `report` komutuyla nakit, gerçekleşen sonuç, masraf, işlem sayısı ve risk raporu.
- Yerel salt okunur web paneli. Chromium'da bakiye/pozisyon/geçmiş ve JavaScript
  hataları kontrol edildi. Windows/Mac masaüstü kurulumu yapılmadı.
- GitHub Actions: Python 3.10/3.12/3.13 için kurulum, test ve demo akışı hazır.
  İlk GitHub run sonucunda üç sürüm de başarılı: https://github.com/fahrettin2001-cloud/jev-crypto-trading-system/actions/runs/43359189952 .

## Kurulum ve kullanım

```bash
python -m pip install -e .
python -m unittest discover -s tests -t . -v
python -m jev --db paper.db init 10000 --risk risk.json
python -m jev --db paper.db report
python -m jev.web --db paper.db --port 8765
```

Panel loopback'e bağlanır. Yerel bilgisayarda tarayıcıdan 8765 portuyla açılır;
bulut ortamında yerel masaüstüne otomatik bağlantı/preview oluşturulmaz.

Şifreli yedek (anahtarı güvenli, ayrı yerde koruyun; kaybedilirse yedek açılamaz):

```bash
python -m jev --db paper.db backup-keygen --key-file local.jevkey
python -m jev --db paper.db backup paper.jevbackup --key-file local.jevkey
python -m jev --db restored.db restore paper.jevbackup --key-file local.jevkey
python -m jev --db restored.db risk-show
python -m jev --db restored.db report
```

Yedekleme anahtarı ve çıktı dosyaları yeni oluşturulur, mevcut dosyalar ezilmez.
Yedek anlık görüntüsü ve geri yükleme doğrulaması SQLite bellek veritabanında yapılır;
uygulama şifresiz geçici dosya üretmez. Yalnızca şifreli yedek ve kullanıcının açıkça
istediği nihai hesap dosyası diske yazılır. Windows yeni dosyaları, miras alınan
izinleri kapatan ve yalnızca mevcut kullanıcıya erişim veren DACL ile oluşturur. Yedek ve anahtarın
ayrı saklanması, hedef depolama ve zamanlanmış görev bu kütüphane tarafından
kurulmaz. Şifreleme için `cryptography>=46,<51` bağımlılığı eklenmiştir.

Ek risk JSON alanları: `max_daily_realized_loss`, `max_total_position_notional`.
Diğer semboller için `--valuation-file` örneği:

```json
{"BTCUSDT":{"price":"50000","observed_at":"2026-11-13T10:00:00+00:00"}}
```

Bu tarih sadece biçimi gösterir; güncel fiyat zamanı sağlanmalıdır. CLI alışındaki
sembolün fiyatı ve gözlem zamanı ayrı komut argümanlarıyla verilir.

## Binance Global

`python -m jev.market BTCUSDT --max-age-seconds 30` sadece resmî piyasa veri
sunucusunun `/api/v3/avgPrice` GET uç noktasını kullanır. Dönen değer son emir
fiyatı veya alış/satış kotasyonu değil, API'nin belirttiği zaman aralığındaki
ortalama fiyattır. Otomatik emir göndermez. Kapanış zamanı, sayısal değerler,
boyut ve yönlendirmeler denetlenir. Timeout/hata/eski veri varsa veri üretilmez.

Resmî kaynak: https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md

Yerel örnek yanıt testleri geçti; canlı isteğin proxy CONNECT aşamasında 403 aldığı
görüldü. `data-api.binance.vision` gereksinimi mevcut `api.github.com` izni
korunarak ortam taslağına kaydedildi. Henüz çalışan politika veya yayın durumu
başarılı varsayılmaz. İzin uygulandıktan sonra canlı sorgu yeniden denenmeli.

## Dış bilgi/erişim bekleyenler

- Jev/Hermes'in kullanılacak gerçek projesi/API'si ve sağlayıcı hesabı.
- Haber kaynağı, içerik erişimi ve test senaryosu.
- Hostinger ürün türü, hedef, işletim sistemi ve yetkili erişim. Hazırlık örneği:
  `deploy/jev-panel.service.example`, açıklama: `DAGITIM-HAZIRLIGI.md`.
- Şifreli yedeklerin konacağı ayrı depolama ve zamanlama hedefi.
- Gerçek emir bağlantısı önceki ayrı tasarım, ekip onayı ve canlı risk testi
  aşamasında kalır; bu değişiklik canlı işlem yetkisi veya bağlantısı eklemez.

Gizli değerler sohbetten istenmez. Gerekli sağlayıcı seçildikten sonra güvenli
ortam ayarları kullanılır. Bu eksikler giderilmeden tüm sistem çalışıyor denmez.

## Son doğrulama notu

Yerel test toplamı 80. İlk 79 test temiz sanal ortam kurulumunda da geçti;
uyumsuz SQLite şemasını reddeden son koruma ayrıca test edildi. CI'nin ilk
79 testlik koşusu Python 3.10, 3.12 ve 3.13'te başarılı oldu. Son commit için
uzak CI sonucu ayrıca kontrol edilmelidir.

## PR #11 entegrasyon düzeltmesi — 14 Kasım 2026

- Güncel main alındı ve GOREVLER.md çakışması iki tarafın bilgisi korunarak çözüldü.
- #14'ün zorunlu politika sürümü kontrolü, #16'nın Windows SQLite bağlantı
  kapatma düzeltmesi korundu. Setter veya sürümsüz politika değişikliği geri gelmedi.
- SQLite alış tutarı üst limiti satışa uygulanmaz. Satışta sembol izin listesi,
  sonlu/pozitif miktar/fiyat ve etkin fiyat güncelliği kontrolü sürer.
- Günlük zarar UTC takvim günüyle hesaplanır; Türkiye saatiyle 03.00'te yeni güne
  geçer. Eski kaydın timestamp'i saat dilimsizse tahmin edilmez, açık hata verilir.
  Geçerli eski kayıtlar değiştirilmez; sadece günlük hesaptaki tarih kaynağı düzelir.
- Backtest günlük kaybı ve diğer sembollerin değerleme fiyatlarını yeni risk
  arayüzüne verir. next_bar modunda gelecekteki kapanışlar yerine bar açılışları
  kullanılır. Bu, bar tabanlı simülasyondur; fiyatların bar içi anlık değerleri bilinmez.
- 235 entegrasyon testi geçti. İki mevcut testte açık CSV ResourceWarning uyarısı
  var; başarısız test yok. UTC gün sınırı, yeniden açma, eski zarar, aynı gün zarar,
  kârdaki satış, satış doğrulamaları ve backtest risk uyumu regresyonlarla kapsanır.
- Hostinger'a dağıtım yapılmadı; çalışan sanal bot değiştirilmedi. Şifreli yedeğin
  geçici dosyaları güvenli silme garantisi vermez; Windows 0o600 kullanıcıya özel
  ACL garantisi değildir. Gerçek hassas veriyle kullanım öncesi bu sınırlar çözülmeli.

## Yedek güvenliği ve kurtarma doğrulaması — 14 Kasım 2026

Şifresiz geçici SQLite dosyaları kaldırıldı: backup API belleğe tutarlı kopya alır,
Python 3.10 uyumlu SQL dökümü bellekte AES-GCM ile şifrelenir. Geri yükleme MAC,
bütünlük ve hesap/politika doğrulamasını bellekte bitirir; sonra yalnızca istenen
nihai yeni dosyayı oluşturur. SQL yüklemesinde ATTACH/DETACH, PRAGMA ve uzantı
yükleme reddedilir. Mevcut dosyalar ezilmez; yazım hatasında yeni çıktı temizlenir.

Yeni yedek biçimi v2'dir. Eski v1 yedekler Python 3.11+ deserialize desteğiyle
bellekte okunabilir; Python 3.10'da açık yükseltme hatası verilir, geçici şifresiz
kopyaya dönülmez. Eski anahtar/yedeklerin ACL'leri otomatik değiştirilmez. Windows
için yeni dosya oluşturma özel DACL'i atomik CreateFile çağrısında verir; 0o600'a
güvenilmez. POSIX'te 0600 kullanılır. Sistem yöneticisi, süreç belleği, swap/pagefile
ve disk şifrelemesi bu uygulama mekanizmasının güven sınırı dışındadır.

`bash deploy/verify-sqlite-recovery.sh` ayrı geçici hesapta yedek/geri yükleme,
kayıtlı politika ve limit üstü satış denemesini doğrular; canlı bot dizinine
veya servislerine dokunmaz. Bu ortamda başarılı çalıştı. Tüm yerel testler:
240 çalıştı, 239 başarılı, yalnızca yerel işletim sisteminde geçerli olmayan
Windows DACL testi atlandı. Windows yedek/DACL testleri GitHub Actions'a eklendi.

Bu oturumda SSH dizini/anahtarı, SSH agent, ortam secret veya sunucu bağlantısı
yok. Hostinger doğrulaması için sunucu adresi, kullanıcı ve güvenli erişim
sağlanmalı. Yerel kurtarma başarısı sunucuda çalıştırılmış gibi raporlanmaz.

## Sonuç — ana dalda

PR #11 birleşti (34b1e2e). Son CI koşusundaki tüm işler başarılı:
https://github.com/fahrettin2001-cloud/jev-crypto-trading-system/actions/runs/43545932280
Python 3.10/3.12/3.13 ve native Windows dosya izinleri doğrulandı. Önceki
bölümlerdeki bekleyen CI/birleştirme notları bu kayıtla güncellenmiştir.
Sunucu erişimi olmadan Hostinger doğrulaması yapılmış sayılmadı.
