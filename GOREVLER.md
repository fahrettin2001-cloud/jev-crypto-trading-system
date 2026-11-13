# Ortak görev dağılımı

Son güncelleme: 13 Kasım 2026

## Amaç ve mevcut durum

Üç kişilik ekip, ileride Binance kripto piyasasında çalışması hedeflenen Jev ve Hermes destekli sistemi geliştirecek. İlk aşama yalnızca çevrimdışı sanal işlemlerden oluşur. Ana dalda sanal işlem çekirdeği (Görev 1, `jev/` paketi) bulunur; SQLite kayıtları ve kalıcılık (Görev 2, PR #5) da ana dala birleşmiştir. Binance Global veya TR seçimi henüz kesinleşmedi. Hostinger bu aşamanın kapsamı dışındadır.

Ekip: @fahrettin2001-cloud, @demirfahrieren-png, @babakok-prog. Aşağıdaki işler öneridir; kimseye onayı olmadan rol atanmadı.

## Çalışmaya başlamadan önce

1. Güncel main dalını ve açık pull request'leri kontrol et. Çalışmayı konuşmada planlayan biri varsa onunla çakışma.
2. Almak istediğin görevin sorumlu alanına GitHub kullanıcı adını ekle; ekip aynı anda değiştirirse güncel sürümü kontrol et. Bir görev başka biri tarafından zaten alındıysa tekrar üstlenme.
3. İlgili işi ayrı bir dalda yap; dosya sahipliğini ve değişiklikleri ekipçe koordine et.
4. Sonucu, test komutunu, nelerin eksik kaldığını ve varsa sorunları pull request veya görev notunda paylaş. Katılımcılar kendi değişikliklerini birleştirebilir; mümkünse bir ekip arkadaşı incelesin.
5. Bu dosyadaki durumu Bekliyor / Çalışılıyor / İncelemede / Tamamlandı olarak güncelle. Bunlar zorunlu otomatik atama değildir.

## Görev 1 — Sanal işlem çekirdeği

- Sorumlu: @demirfahrieren-png
- Durum: İncelemede — çekirdek main'de (PR #2); arayüz notu: docs/gorev1-arayuz.md
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
- Ek risk geliştirmesi: `feat/pozisyon-nakit-risk` dalında incelemeye hazır; henüz ana dala birleşmedi. Asgari nakit rezervi ve sembol başına pozisyon değeri sınırı eklendi; dalda 39 test geçti (30 temel + 9 genişletme).

## Görev 3 — Proje hafızası ve entegrasyon tasarımı

- Sorumlu: @fahrettin2001-cloud ve bu sohbetteki ajan
- Durum: Çalışılıyor
- Kapsam: Obsidian ile okunabilir proje notları, ekip çalışma rehberi, geri yükleme ve ilerideki Jev / Hermes / haber sistemi arayüzlerinin tasarımı.
- Çıktı: Kısa proje özeti, teknik karar ve görev notu şablonları; GitHub kod/not yedeği ve şifreli veritabanı yedeği için plan.
- Bitti ölçütü: Yeni bir ekip üyesi README ve notları okuyup ilk aşamayı, testleri ve açık kararları anlayabilmeli.
- Sınır: Otomatik yedekleme kurulduğunu iddia etme. Hostinger'da veya gerçek hesaplarda işlem yapma.

## İleriki aşamalar — Henüz başlanmadı

- [ ] Binance Global / Binance TR seçimi ve yalnızca halka açık piyasa verisi.
- [ ] Haber kaynağı, Jev ve güçlü model bağlantılarının test ortamında değerlendirilmesi.
- [ ] Sanal işlem sonuçlarının masraf ve riskle birlikte ölçülmesi.
- [ ] Hostinger üzerinde dağıtım ve yedekleme, ayrı plan ve testlerden sonra.
- [ ] Gerçek emir bağlantısı, ancak sanal testler ve ekip değerlendirmesinden sonra ayrı aşama.

## Güvenlik ve veri

API anahtarı, şifre, hesap bilgisi ve .env gibi gizli dosyaları GitHub'a veya ortak notlara eklemeyin. Örnek ayarlarda gerçek veri kullanmayın. Bu görev listesi veya model kararı gerçek işlem yetkisi vermez; ileride canlı emirler için bağımsız ve test edilmiş risk kontrolü gerekir.

## Açık kararlar

- Hangi borsa: Binance Global mi Binance TR mi?
- İlk sanal bütçe, işlem çiftleri ve örnek komisyon oranı?
- Üç görevden hangisini kim üstlenecek?
- Strateji, risk sınırları ve haber kaynakları?
