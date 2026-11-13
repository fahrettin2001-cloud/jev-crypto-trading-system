# Sanal portföy komut satırı

Depo kökünde Python 3.10+ ile çalışır; dış bağımlılık gerekmez. PR #3'ün farklı
kalıcılık yaklaşımını kullanmaz; mevcut `SQLitePortfolio` ve `RiskLimits`
üzerinden çalışır. Gerçek borsa emri göndermez, fiyatlar elle sağlanır.

## Hesap ve işlemler

Önce `risk.json` dosyası oluşturun (değerler yalnızca örnektir):

```json
{
  "max_trade_notional": "1000",
  "allowed_symbols": ["BTCUSDT", "ETHUSDT"],
  "min_cash_reserve": "2000",
  "max_position_notional": "3000"
}
```

```bash
python -m jev --db paper.db init 10000 --risk risk.json
python -m jev --db paper.db buy BTCUSDT 0.01 50000 --risk risk.json
python -m jev --db paper.db sell BTCUSDT 0.005 51000 --maker --risk risk.json
python -m jev --db paper.db status
python -m jev --db paper.db history
```

`--db` komuttan önce yazılır. Çıktılar JSON'dur; parasal değerler hassasiyeti
korumak için metin olarak yazılır. `status`, nakit, başlangıç bakiyesi,
pozisyonlar, toplam komisyon ve gerçekleşen kâr/zararı verir. Güncel piyasa
fiyatları alınmadığı için toplam piyasa değeri veya gerçekleşmemiş kârı hesaplamaz.

`init` mevcut hiçbir dosyayı değiştirmez; farklı dosya adı seçin. Başlangıçta
`--quote`, `--maker-rate`, `--taker-rate` kullanılabilir. Diğer komutlar dosya veya
şema oluşturmaz; eksik/uyumsuz hesapta hata verir. Hatalar stderr'e yazılır ve
çıkış kodu 1 olur; komut sözdizimi hatalarında argparse çıkış kodu 2 döndürür.

## Risk politikası ve fiyat zamanı

Risk politikası hesapta kalıcıdır. İşlemde `--risk` isteğe bağlıdır; verilirse kayıtlı politikayla eşit olmalıdır. Bilinmeyen politika alanları reddedilir.
Boş `{}` dosyasının init/risk-set ile açıkça seçilmesi isteğe bağlı limitleri kapatır; sayısal
girdi ve bakiye kontrolleri yine uygulanır. Risk dosyası güvenilir yerel ayardır;
yalnızca init veya açık risk-set komutuyla veritabanına kaydedilir.

Güncellik kontrolü için risk JSON'una `"max_price_age_seconds": 30` ekleyin ve
alış/satışta `--price-observed-at` ile saat dilimli gerçek gözlem zamanını sağlayın:

```text
--price-observed-at 2026-11-13T10:00:00+00:00
```

Bu sabit tarih kullanım biçimini gösterir; güncellik limiti açıkken eski tarihle
çalıştırılan komut reddedilir. CLI her zaman mevcut sistem saatini kullanır;
işlem tarihini veya kontrol saatini geri alma seçeneği yoktur. Tarihsel simülasyon
Python API'sindeki güvenilir saat sağlayıcıyla yapılır. Gözlem zamanı verilmezse
veya çok eski/gelecekteyse güncellik politikası etkin olan işlem reddedilir.

## Doğrulama

`python -m unittest discover -s tests -t .` ile 60 test geçti. CLI testleri ayrı
Python süreçlerinde bakiye/pozisyon/geçmiş, maker komisyonu, yeniden açma,
mevcut dosyayı koruma, eksik/uyumsuz dosyayı değiştirmeme ve risk reddi senaryolarını
çalıştırır. Veritabanları geçici klasörlerde tutulur.

Kalıcı politika, eski hesapların göçü ve `risk-show`/`risk-set`: [inceleme](RISK-KALICILIK-INCELEMESI.md).
