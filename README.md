# Jev kripto işlem sistemi

Bu proje, kripto piyasasını ve haberleri izleyen, Jev ve güçlü bir modelle değerlendirme yapan bir sistemin geliştirilmesini hedefler. Başlangıç yalnızca sanal işlemdir. Henüz çalışan Binance, Jev veya Hermes bağlantısı yoktur.

## İlk aşama

1. Çevrimdışı örnek fiyatlarla çalışan sanal portföy ve komisyon hesapları.
2. Testler ve bağımsız risk kontrolleri.
3. Seçilecek borsadan halka açık verilerin okunması.
4. Haber, Jev ve güçlü model entegrasyonlarının test edilmesi.
5. Obsidian proje notları ve güvenli yedekleme planı.

## Sanal portföy (görev 1)

Python 3.10+ gerekir, dış bağımlılık yoktur. Tutarlar `Decimal` ile hesaplanır.

- `jev/fees.py`: maker/taker komisyon oranları (varsayılan %0,1)
- `jev/portfolio.py`: nakit, pozisyonlar, alım-satım, ortalama maliyet, gerçekleşen/gerçekleşmemiş kâr-zarar
- `jev/prices.py`: `data/sample_prices.csv` dosyasından çevrimdışı fiyat okuma
- `data/sample_prices.csv`: uydurma örnek fiyatlar (gerçek piyasa verisi değildir)

Varsayımlar: komisyon karşı para biriminden (USDT) alınır ve ortalama maliyete eklenir. Açığa satış ve kaldıraç yoktur. Yetersiz nakit veya miktar varsa işlem reddedilir.

```bash
python -m unittest discover -s tests -t .   # testler
python -m examples.demo                     # örnek senaryo
```

## Ekipçe çalışma

Her iş için ayrı dal açın, testleri çalıştırın ve değişiklikleri pull request ile incelemeye sunun. API anahtarlarını, şifreleri, gerçek hesap bilgilerini ve gizli yapılandırmaları repoya koymayın.

## Belirlenecek kararlar

- Binance Global mi Binance TR mi?
- İlk izlenecek işlem çiftleri ve sanal bütçe.
- Üç kişinin görev dağılımı.
- Başlangıç risk limitleri ve haber kaynakları.

Gerçek emir ve canlıya geçiş, sanal testler ve ayrıca değerlendirme sonrasında ele alınacaktır.

## ChatGPT bağlantı testi

Bu not, ChatGPT’nin GitHub deposuna yazma erişimini doğrulamak için eklendi.

## Kalıcı sanal portföy

Aynı `jev.Portfolio` sınıfı hem bellekte hem SQLite üzerinde çalışır. Kalıcı portföy için:

```bash
python3 -m jev --db portfolio.sqlite3 init 10000 --quote USDT
python3 -m jev --db portfolio.sqlite3 buy BTCUSDT 0.01 50000
python3 -m jev --db portfolio.sqlite3 sell BTCUSDT 0.005 51000 --maker
python3 -m jev --db portfolio.sqlite3 status
python3 -m jev --db portfolio.sqlite3 history
python3 -m unittest discover -s tests -t .
```

`init` mevcut portföyü sıfırlamaz; varsayılan dosya `portfolio.sqlite3` Git'e eklenmez. Başlangıçta `--maker-rate` ve `--taker-rate` ile komisyon oranları ayarlanabilir (`0.001` = %0,1). Fiyatlar elle girilir; `data/sample_prices.csv` çevrimdışı örneklerdir.

Python API'sinde `Portfolio.create(dosya, cash)` yeni portföy oluşturur, `Portfolio.open(dosya)` kaydedilmiş portföyü açar; `close()` veya `with` ile bağlantıyı kapatın. Mevcut `Portfolio(cash=...)` kullanımı bellek içi çalışmaya devam eder. Her kalıcı alış veya satışta bakiye, pozisyon ve işlem kaydı tek SQLite işlemiyle güncellenir; hata durumunda tümü geri alınır. Birden fazla bağlantıda her işlem en son kaydedilmiş durumu kullanır; başka bağlantıların değişikliklerini görüntülemek için portföyü yeniden açın. Harici servis bağlantısı ve gerçek emir yoktur.
