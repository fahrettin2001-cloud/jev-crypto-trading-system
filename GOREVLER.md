# Ortak görev dağılımı

Son güncelleme: 13 Kasım 2026

## Amaç ve mevcut durum

Üç kişilik ekip, ileride Binance kripto piyasasında çalışması hedeflenen Jev ve Hermes destekli sistemi geliştirecek. Ana dalda sanal işlem çekirdeği (Görev 1), SQLite kayıtları ve kalıcı risk politikası (Görev 2) bulunur. Borsa olarak Binance Global seçildi ([karar kaydı](docs/kararlar/2026-11-13-binance-global.md)). Hostinger'daki canlı verili sanal çalışma Görev 5.3 kapsamındadır; bu oturumda sunucuya doğrudan erişilmedi.

Ekip: @fahrettin2001-cloud, @demirfahrieren-png, @babakok-prog. Aşağıdaki işler öneridir; kimseye onayı olmadan rol atanmadı.

## Çalışmaya başlamadan önce

1. Güncel main dalını ve açık pull request'leri kontrol et. Çalışmayı konuşmada planlayan biri varsa onunla çakışma.
2. Almak istediğin görevin sorumlu alanına GitHub kullanıcı adını ekle; ekip aynı anda değiştirirse güncel sürümü kontrol et. Bir görev başka biri tarafından zaten alındıysa tekrar üstlenme.
3. İlgili işi ayrı bir dalda yap; dosya sahipliğini ve değişiklikleri ekipçe koordine et.
4. Her çalışma sonunda yapılan yenilikleri, test sonuçlarını ve açık işleri `docs/PROJE_HAFIZASI.md` ile ilgili görev notunda güncelle; yetkin ve erişimin varsa ayrı dalda commit/push edip PR aç veya mevcut PR'ı güncelle. Paylaşım ve doğrulama ayrıntıları için proje hafızasındaki 'Her çalışma sonunda GitHub ve hafızayı güncelleme' bölümünü uygula. Katılımcılar kendi değişikliklerini verilen görev talimatlarına uyarak birleştirebilir; mümkünse bir ekip arkadaşı incelesin.
5. Bu dosyadaki durumu Bekliyor / Çalışılıyor / İncelemede / Tamamlandı olarak güncelle. Bunlar zorunlu otomatik atama değildir.

## Görev 1 — Sanal işlem çekirdeği

- Sorumlu: @demirfahrieren-png
- Durum: Tamamlandı — PR #2 ve #4 ana dala birleşti (13 Kasım 2026). Görev 2'nin `SQLitePortfolio` katmanı çekirdeği değiştirmeden kullanıyor; ana dalda 60 test geçti (13 Kasım akşamı yeniden çalıştırıldı). Arayüz notu: docs/gorev1-arayuz.md
- Kapsam: Python proje altyapısı, ortak veri modelleri, sanal portföy ve alış/satış.
- Çıktı: Decimal ile tutarlı tutar ve komisyon hesapları; geçersiz fiyat/miktar, yetersiz para veya varlığın reddi.
- Sınır: Sadece örnek veri ve sanal bakiye; borsa veya harici servis bağlantısı yok.
- Bitti ölçütü: Başarılı ve reddedilen işlemler için testler ve kısa çalıştırma yönergesi.
- Koordinasyon: Görev 2 başlamadan veri modelleri, metot imzaları ve işlem akışı ekipçe netleştirilir.

## Görev 2 — Kayıtlar ve güvenlik testleri

- Sorumlu: @babakok-prog
- Durum: Tamamlandı — PR #5 ana dala birleşti (13 Kasım 2026).
- Kapsam: SQLite işlem kayıtları, bakiye kalıcılığı ve bağımsız risk kontrolü taslağı.
- Çıktı: İşlem ile bakiye değişikliği tek veritabanı işlemiyle kaydedilir; hata durumunda tamamı geri alınır. Yeniden başlatma sonrası hesap doğru yüklenir.
- Bitti ölçütü: Başarılı kayıt, yeniden açma, yetersiz bakiye ve hata/geri alma senaryolarını doğrulayan testler.
- Bağımlılık: Görev 1 ile önceden anlaşılan arayüz. Entegrasyon için diğer dalın hazır olması gerekebilir.
- Not: Sayısal risk limitleri ekipçe seçilene kadar örnek ve değiştirilebilir olarak işaretlenir.

- Uygulama: `SQLitePortfolio`, bağımsız `RiskLimits` taslağı ve kalıcılık/geri alma testleri eklendi. `python -m unittest discover -s tests -t . -v`: 30 test geçti. Kullanım ve sınırlar: `docs/gorev2-kayitlar.md`.
- Ek risk geliştirmesi: PR #6 ana dala birleşti. Asgari nakit rezervi ve sembol başına pozisyon değeri sınırı eklendi. Geliştiren ajan dalda 39 test geçtiğini bildirdi; bu notu güncelleyen ajan testleri yeniden çalıştırmadı.

## Görev 3 — Proje hafızası ve entegrasyon tasarımı

- Sorumlu: @fahrettin2001-cloud ve bu sohbetteki ajan
- Durum: Çalışılıyor — ortak hafıza, Jev ilk denemesi ve yedekleme durumu güncelleniyor; ayrıntı `docs/PROJE_HAFIZASI.md`.
- Kapsam: Obsidian ile okunabilir proje notları, ekip çalışma rehberi, geri yükleme ve ilerideki Jev / Hermes / haber sistemi arayüzlerinin tasarımı.
- Çıktı: Kısa proje özeti, teknik karar ve görev notu şablonları; GitHub kod/not yedeği ve şifreli veritabanı yedeği için plan.
- Bitti ölçütü: Yeni bir ekip üyesi README ve notları okuyup ilk aşamayı, testleri ve açık kararları anlayabilmeli.
- Sınır: Otomatik yedekleme kurulduğunu iddia etme. Hostinger'da veya gerçek hesaplarda işlem yapma.

## Görev 4 — Strateji arayüzü, backtest ve Binance işlem kuralları

- Sorumlu: @demirfahrieren-png
- Durum: Tamamlandı — PR #15 ana dala birleşti; ilk gerçek Binance verisiyle backtest 13 Kasım 2026'da çalıştırıldı (sonuçlar `docs/gorev4-backtest.md`).
- Kapsam: Strateji/öneri arayüzü (ileride Jev'in bağlanacağı yer), geçmiş fiyatlarla backtest, piyasa/limit emir, zarar durdur / kâr al, kayma ve likidite sınırı, performans ölçümü, Binance Global `exchangeInfo` işlem kuralları ve halka açık veri indirme aracı.
- Çıktı: `python -m jev.backtest` (rapor + `--out` ile CSV/JSON), `python -m jev.binance_data` (SHA-256 doğrulamalı indirme).
- Sınır: Gerçek emir, hesap veya API anahtarı yok. Testler sentetik veriyle çalışır; gerçek veri `python -m jev.binance_data` ile indirilir.
- Bitti ölçütü: Testler (geleceği görmeme, komisyon/kayma, emir türleri, kurallar, risk reddi, indirme doğrulaması) ve gerçek Binance verisiyle bir backtest çalıştırılması (tamamlandı).
- Ayrıntı: `docs/gorev4-backtest.md`. Test: `python -m unittest discover -s tests -t .` → 148 test geçti.

## Görev 5 — Botu geliştirme: ölçüm, risk ve yeni sinyaller

- Sorumlu: @demirfahrieren-png
- Durum: Devam ediyor — 5.1 (PR #21), 5.2 (PR #22) ve 5.3 (PR #23, #24, #26) ana dala birleşti. 5.4 (haber duygu analizi) sırada.
- Canlı sanal işlem (13 Kasım 2026): Hostinger sunucusuna kuruldu ve doğrulandı. 500 USDT sanal bakiye, BTCUSDT + ETHUSDT, saatlik çalışma (`jev-live.timer`, her saat :01). Kurulum: `docs/CANLI-SANAL-ISLEM.md`.
- Sonuçlar: Her sabah 08:20'de (TR) herkese açık [`demirfahrieren-png/jev-canli-sonuclar`](https://github.com/demirfahrieren-png/jev-canli-sonuclar) deposuna yayınlanıyor (`jev-sonuc.timer`, yalnızca o depoya yazabilen deploy key). `son/durum.txt` güncel durumu, `son/islemler.csv` işlemleri gösterir.
- Kapsam: 5.1 oynaklığa göre pozisyon büyüklüğü, 5.2 karar günlüğü ve güven kalibrasyonu, 5.3 canlı sanal işlem, 5.4 haber duygu analizi. Jev bağlantısı (@fahrettin2001-cloud) bu görevin dışında.
- Sınır: Gerçek emir, hesap veya API anahtarı yok. 5.3 ve 5.4'ün canlı kısımları ağ erişimi olan bir ekip bilgisayarında çalıştırılacak.
- Ayrıntı: `docs/gorev5-gelistirmeler.md`.

## Görev 6 — Yapay sinir ağı ve ödül sistemi araştırması

- Sorumlu: @fahrettin2001-cloud ve bu sohbetteki ajan.
- Durum: Planlandı; takip [#29](https://github.com/fahrettin2001-cloud/jev-crypto-trading-system/issues/29).
- Kapsam: Sentetik veriyle küçük sinir ağı deneyi; daha sonra geçmiş verilerde ayrı değerlendirme; sanal sonuçlardan maliyet ve riski gözeten ödül kaydı tasarımı.
- Sınır: Jev'in modeli yeniden eğitilmez; çalışan Hostinger botuna bağlanmaz ve emir verilmez. Bağımsız risk sistemi korunur.
- Bitti ölçütü ve iş sırası: [Görev 6 tasarımı](docs/GOREV6-SINIR-AGI-ODUL.md). PR #27 ayrı bir gölge ölçüm taslağıdır; sinir ağı değildir.

## İleriki aşamalar — Henüz başlanmadı

- [ ] Binance Global (seçildi, [karar kaydı](docs/kararlar/2026-11-13-binance-global.md)) için yalnızca halka açık piyasa verisi ve işlem kuralları (`exchangeInfo`).
- [ ] Haber kaynağı, Jev ve güçlü model bağlantılarının test ortamında değerlendirilmesi. Başlangıç için [haber kaynakları ve ajan kuralları](docs/HABER-KAYNAKLARI.md): önce çevrimdışı örnekler; CryptoPanic ve Binance duyuruları henüz bağlı değil.
- [ ] Sanal işlem sonuçlarının masraf ve riskle birlikte ölçülmesi. Görev 4'te başlandı (backtest ve ölçümler); gerçek veriyle çalıştırma bekliyor.
- [ ] Hostinger üzerinde yedekleme. Sanal işlem dağıtımı Görev 5.3 kapsamında yapıldı.
- [ ] Gerçek emir bağlantısı, ancak sanal testler ve ekip değerlendirmesinden sonra ayrı aşama.

## Güvenlik ve veri

API anahtarı, şifre, hesap bilgisi ve .env gibi gizli dosyaları GitHub'a veya ortak notlara eklemeyin. Örnek ayarlarda gerçek veri kullanmayın. Bu görev listesi veya model kararı gerçek işlem yetkisi vermez; ileride canlı emirler için bağımsız ve test edilmiş risk kontrolü gerekir.

## Açık kararlar

- ~~Hangi borsa: Binance Global mi Binance TR mi?~~ → Binance Global ([karar kaydı](docs/kararlar/2026-11-13-binance-global.md)). Türkiye'den gerçek hesap kullanımının yasal durumu canlı aşamadan önce kontrol edilecek.
- İşlem çiftleri: BTCUSDT + ETHUSDT önerildi ([karar önerisi](docs/kararlar/2026-11-13-cift-ve-risk-limitleri.md)) — ekip onayı bekliyor.
- Risk limitleri: "temkinli" paket önerildi (işlem başına %10, tek coinde %30, nakitte en az %40, günlük zarar %2) — ekip onayı bekliyor.
- İlk sanal bütçe ve örnek komisyon oranı? (bütçe ekiple konuşulacak)
- Üç görevden hangisini kim üstlenecek?
- Strateji, risk sınırları ve haber kaynakları?

## Ek risk geliştirmeleri — 13 Kasım 2026

- Asgari nakit ve sembol pozisyon sınırları PR #6 ile ana dala birleşti.
- Fiyat güncelliği: PR #7 ile ana dala birleşti. İsteğe bağlı yaş limiti, ayrı gözlem zamanı ve güvenilir kontrol
  saati eklendi. Alış/satışta eski, eksik veya gelecekteki fiyat zamanı reddedilir.
- Doğrulama: `python -m unittest discover -s tests -t .` — 52 test geçti.
- Örnek limitler ekip kararı değildir; borsa ve ajan bağlantısı kurulmadı.

## Terminal arayüzü — ana dalda

- Dal: `feat/portfoy-cli`; PR #8 ile ana dala birleşti.
- `python -m jev`: hesap oluşturma, alış, satış, durum ve geçmiş komutları.
- Mevcut SQLite/risk katmanı kullanılır; her işlemde risk dosyası açıkça seçilir.
- 60 test geçti (52 mevcut, 8 CLI süreç testi). Kullanım: `docs/CLI.md`.
- Açık PR #3'teki farklı kalıcılık yaklaşımı birleştirilmedi veya kapatılmadı.

## Yeni hazırlıklar — inceleme dalları

- `fix/kalici-risk-politikasi` / PR #10: Fahrettin'in yeniden açılış talebi
  incelendi; politikasız açılışta limitlerin kaybolduğu doğrulandı. Kalıcı,
  sürümlü politika ve politikasız işlem reddi uygulandı. Rapor:
  `docs/RISK-KALICILIK-INCELEMESI.md`.
- `feat/gelistirme-altyapisi`: PR #10 üzerine kurulu; şifreli yedek/geri yükleme,
  günlük gerçekleşen zarar ve tüm pozisyonların değer sınırı, rapor, yerel
  görüntüleme paneli, salt okunur Binance Global adaptörü ve GitHub Actions.
- Yerel ve temiz sanal ortamda ilk 79 test geçti; uyumsuz şema korumasıyla güncel yerel toplam 80 testtir. CLI yedek/geri yükleme ve Chromium
  panel kontrolü de geçti. Ayrıntılı kullanım ve dış erişim bekleyen işler:
  `docs/GELISTIRME-DURUMU.md`. Ana dala birleşmiş sayılmamalıdır.
- Halka açık veri için kullanıcı Binance Global'i seçti; fiyat sorgusu ortamın
  ağ politikasında engelli. Alan adı gereksinimi taslağa kaydedildi, yayımlanmadı.
- Jev/Hermes sağlayıcısı, haber kaynağı, Hostinger hedefi ve ayrı yedek depolama
  seçimi bekleniyor. Gerçek emir bağlantısı uygulanmadı.

## Görev 2 / PR #11 inceleme düzeltmeleri — 14 Kasım 2026

- Sorumlu: @babakok-prog. Durum: PR #11 güncellendi; ana dala birleşmedi.
- PR #16 zaten #11 dalında; #14'ün risk sürümü koruması ile güncel main alındı.
- Eski kayıtlardaki günlük zarar kalıcı alış kilidi ve değer kazanan pozisyonun
  tutar sınırı yüzünden satılamaması düzeltildi; UTC/yeniden açma testleri eklendi.
- Backtest günlük kayıp ve zamanlı fiyat verilerini genişletilmiş risk katmanına
  geçiriyor; next_bar için diğer sembollerin gelecek kapanışını kullanmıyor.
- 235 test geçti. GitHub CI sonucu PR #11 üzerinden kontrol edilmeli. Ayrıntı:
  `docs/GELISTIRME-DURUMU.md`. Hostinger botuna dağıtım yapılmadı.
