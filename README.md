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

## Kalıcı kayıtlar (görev 2)

`SQLitePortfolio` bakiye, pozisyonlar ve işlem geçmişini aynı SQLite işlemiyle saklar.
Program yeniden açıldığında hesap yüklenir; başarısız yazım tamamen geri alınır.
Dış bağımlılık gerekmez. Kullanım, risk taslağı ve sınırlar: [Görev 2](docs/gorev2-kayitlar.md).

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
