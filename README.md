# Jev kripto işlem sistemi

Bu proje, kripto piyasasını ve haberleri izleyen, Jev ve güçlü bir modelle değerlendirme yapan bir sistemin geliştirilmesini hedefler. Başlangıç yalnızca sanal işlemdir. Henüz çalışan Binance, Jev veya Hermes bağlantısı yoktur.

## İlk aşama

1. Çevrimdışı örnek fiyatlarla çalışan sanal portföy ve komisyon hesapları.
2. Testler ve bağımsız risk kontrolleri.
3. Seçilecek borsadan halka açık verilerin okunması.
4. Haber, Jev ve güçlü model entegrasyonlarının test edilmesi.
5. Obsidian proje notları ve güvenli yedekleme planı.

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

## Çevrimdışı sanal portföy

Python 3.10 veya daha yenisi yeterlidir; çalıştırmak ve test etmek için ek paket gerekmez. Komutları depo kökünden çalıştırın:

```bash
export PYTHONPATH=src
python3 -m trading --db portfolio.sqlite3 init 10000 --quote USDT
python3 -m trading --db portfolio.sqlite3 buy BTC 0.01 50000 --fee-rate 0.001
python3 -m trading --db portfolio.sqlite3 sell BTC 0.005 51000 --fee-rate 0.001
python3 -m trading --db portfolio.sqlite3 status
python3 -m trading --db portfolio.sqlite3 history
python3 -m unittest discover -s tests -v
```

`init` yalnızca yeni bir portföy için bir kez çalışır; mevcut bakiyeyi sıfırlamaz. `--db` verilmezse `portfolio.sqlite3` kullanılır. Her komutta aynı dosya seçilirse portföy ve geçmiş yeniden açılır. Bu dosyayı koruyun; Git'e eklenmez.

Fiyatı kendiniz girersiniz; `data/sample_prices.json` çevrimdışı örnek değerler içerir, otomatik fiyat kaynağı değildir. Komisyon oranı ondalık kesirdir: `0.001`, %0,1 anlamına gelir. Alış toplamı fiyat × miktar + komisyon, satış toplamı fiyat × miktar − komisyondur; komisyon karşıt para biriminden alınır. Hesaplar `Decimal` ile yapılır. API kullanırken miktarları ve fiyatları `"0.1"` gibi metin veya `Decimal` olarak verin, `float` kullanmayın.

Bakiyeler ve başarılı işlem kayıtları aynı SQLite işleminde güncellenir. Yetersiz bakiye, geçersiz veri veya kayıt sırasında hata durumunda işlem geri alınır. Fiyat verileri örnektir; dış servis bağlantısı ve gerçek emir gönderimi yoktur.
