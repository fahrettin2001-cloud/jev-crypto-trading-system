# Geliştirme durumu — 13 Kasım 2026

Bu çalışma kalıcı risk politikası PR #10 üzerine kuruludur. Henüz ana dala
birleştirilmiş gibi değerlendirilmemelidir.

## Hazırlanan ve yerelde doğrulananlar

- AES-256-GCM şifreli SQLite yedeği, backup API ile WAL dahil tutarlı kopya,
  bütünlük/anahtar doğrulaması ve mevcut hesabı ezmeyen geri yükleme.
- Günlük gerçekleşen kayıp limiti: UTC yürütme günündeki negatif gerçekleşen
  sonuçların mutlak toplamı. Kârlar kaybı silmez. Eşik dolunca yeni alış durur;
  satış sürer. Açık pozisyonun gerçekleşmemiş zararı bu limit değildir.
- Eski yürütme zamanı bilinmeyen kayıtların kayıpları ihtiyatlı biçimde sayılır.
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
Ham SQLite kopyası sadece erişimi sınırlandırılmış geçici klasörde oluşturulur,
işlem sonunda kaldırılır; çıktı kimlik doğrulamalı şifrelidir. Yedek ve anahtarın
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
