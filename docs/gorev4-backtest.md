# Görev 4 — Strateji arayüzü, backtest ve Binance işlem kuralları

Durum: İncelemede — 13 Kasım 2026 (@demirfahrieren-png, Claude ile). PR #15, ana dala birleşmedi.

## Neden?

Ana dalda işlemleri doğru kaydeden ve risk kurallarını uygulayan bir sanal portföy var; ancak (1) işleme kimin, neye göre karar verdiği tanımlı değildi ve (2) kararların iyi olup olmadığını ölçen bir şey yoktu. Jev / güçlü model bağlanmadan önce aynı hattın basit bir stratejiyle uçtan uca test edilmesi ve sonuçların masraf ve riskle birlikte ölçülmesi gerekiyor (GOREVLER.md "İleriki aşamalar" maddesi).

## Eklenenler

| Dosya | İçerik |
|---|---|
| `jev/strategy.py` | `Bar` (OHLC + hacim), `OrderIntent` (piyasa / limit, zarar durdur, kâr al), salt okunur `PortfolioView`, `Strategy` arayüzü; örnek `BuyAndHold` ve `SmaCross` |
| `jev/backtest.py` | Backtest motoru, kayma, likidite sınırı, metin raporu, CSV/JSON dışa aktarma, `python -m jev.backtest` |
| `jev/metrics.py` | Toplam getiri, en büyük düşüş, kazanan satış oranı, komisyon payı |
| `jev/exchange_rules.py` | Binance Global `exchangeInfo` filtreleri: LOT_SIZE, MARKET_LOT_SIZE, PRICE_FILTER, NOTIONAL/MIN_NOTIONAL |
| `jev/klines.py` | Basit CSV ve data.binance.vision kline CSV'lerinden OHLCV bar okuma (ms ve µs zaman damgası) |
| `jev/binance_data.py` | Halka açık veriyi indirme aracı: exchangeInfo ve aylık kline arşivleri, SHA-256 doğrulamalı (`python -m jev.binance_data`) |
| `data/exchange_info_sample.json` | **Örnek, doğrulanmamış** exchangeInfo (BTCUSDT, ETHUSDT) |
| `data/synthetic_prices.csv`, `data/synthetic_klines/`, `examples/sentetik_veri.py` | **Sentetik** 90 günlük saatlik fiyat (basit CSV ve Binance kline biçiminde OHLCV); sabit tohumla üretilir |
| `data/binance/` | İndirilen gerçek verinin yeri; içeriği git'e eklenmez |
| `tests/test_strategy.py`, `test_backtest.py`, `test_backtest_orders.py`, `test_exchange_rules.py`, `test_binance_data.py` | 88 yeni test |

Mevcut modüller (`portfolio`, `fees`, `risk`, `storage`, `__main__`) değiştirilmedi; açık PR'larla kod dosyası çakışması yok.

## Bir barda ne olur?

Bar zamanı barın **kapanış** zamanıdır. Sırasıyla:

1. **Koruyucu çıkışlar** (önceki barlarda açılmış pozisyonlar): açılış seviyenin ötesindeyse (fiyat boşluğu) açılıştan, değilse barın düşüğü zarar durdura inerse ya da yükseği kâr ala çıkarsa o seviyeden satılır. Aynı barda ikisi de değdiyse hangisinin önce olduğu bilinemediği için **zarar durdur** varsayılır. Pozisyonun açıldığı barda kontrol yapılmaz (alıştan önce mi sonra mı bilinemez).
2. **Bekleyen piyasa emirleri** (önceki barın kapanışında verilen): bu barın **açılış** fiyatından + kayma, taker komisyonu.
3. **Limit emirler** (önceki barlarda verilen): alış limiti barın düşüğü limite inerse, satış limiti yükseği limite çıkarsa gerçekleşir; açılış limitten iyiyse açılıştan. Maker komisyonu, kayma yok. `good_for_bars` bar içinde gerçekleşmezse "süresi doldu" olarak reddedilir.
4. Stratejiye salt okunur görünüm verilir; yeni öneriler alınır.
5. Portföy son bilinen kapanışlarla değerlenir.

Her gerçekleşmede: miktar Binance adımına **aşağı** yuvarlanır → işlem kuralları → likidite sınırı → `RiskLimits.check` → deneme portföyünde işlem → `check_after_buy`. Herhangi biri geçmezse portföy değişmez, red nedeniyle kaydedilir.

İncelemede tartışılması gereken tasarım kararları:

- **Zarar durdur ve kâr al risk limitine ve likidite sınırına takılmaz**, yalnızca işlem kuralları uygulanır. Aksi halde örneğin işlem başına azami tutar yükselmiş bir pozisyonun kapanmasını engelleyebilir. Ekip farklı isterse tek satırla değişir.
- Zarar durdur piyasa emri gibi (taker + kayma), kâr al limit emri gibi (maker, kaymasız) modellenir.
- Kurallar açıkken zarar durdur / kâr al seviyeleri tick adımına **yukarı** yuvarlanır (temkinli yön).
- Limit emir için nakit ayrılmaz; gerçekleştiği anda nakit yetmezse reddedilir.
- `execution="same_bar"` (komut satırında `--same-bar`) piyasa emrini aynı barın kapanışından yürütür; geleceği görme hatası içerir, yalnızca farkı görmek için.

## Kullanım

### 1. Gerçek veriyi indir (kendi bilgisayarında; ağ gerekir)

```bash
python -m jev.binance_data --symbols BTCUSDT ETHUSDT --interval 1h --start 2026-08 --end 2026-10
```

`data/binance/exchange_info.json` ve her ay için doğrulanmış `BTCUSDT-1h-2026-08.csv` gibi dosyalar yazılır; komut sonunda hazır backtest komutunu yazdırır. Aylık arşiv o ay bittikten sonra yayımlanır. Anahtar gerekmez; yalnızca halka açık veri okunur.

### 2. Backtest

```bash
# Gerçek veriyle (1. adımdan sonra)
python -m jev.backtest --symbol BTCUSDT \
    --prices data/binance/BTCUSDT-1h-2026-08.csv data/binance/BTCUSDT-1h-2026-09.csv data/binance/BTCUSDT-1h-2026-10.csv \
    --kline-symbols BTCUSDT BTCUSDT BTCUSDT --rules data/binance/exchange_info.json \
    --fast 24 --slow 96 --stop-loss-pct 0.04 --take-profit-pct 0.08 --max-volume-share 0.01 \
    --out sonuclar/

# Sentetik veriyle (ağ gerekmez)
python -m jev.backtest --prices data/synthetic_klines/BTCUSDT-1h-sentetik.csv \
    --kline-symbols BTCUSDT --rules data/exchange_info_sample.json --fast 24 --slow 96
```

Seçenekler: `--strategy sma|al-tut`, `--fraction`, `--cash`, `--taker-rate`, `--maker-rate`, `--slippage-bps` (varsayılan 5), `--max-trade-notional`, `--max-volume-share`, `--stop-loss-pct`, `--take-profit-pct`, `--out`, `--same-bar`. `python -m jev.backtest -h`.

`--out` klasörüne `islemler.csv` (tür ve gerekçe dahil), `varlik_egrisi.csv`, `redler.csv` ve `ozet.json` yazılır; tutarlar kayıpsız metin olarak.

### Python'dan / yeni strateji

```python
from jev.backtest import BacktestConfig, run_backtest, format_report
from jev.klines import load_bars
from jev.strategy import BUY, LIMIT, OrderIntent

class Ornek:
    name = "ornek"
    def on_bar(self, bar, view):
        # Pozisyon yoksa ve bekleyen emir yoksa yeni limit alış ver
        if view.quantity("BTCUSDT") == 0 and not view.open_orders:
            price = bar.prices["BTCUSDT"]
            return [OrderIntent("BTCUSDT", BUY, quote_amount=view.cash / 2,
                                order_type=LIMIT, limit_price=round(price * 99 / 100, 2),
                                good_for_bars=3, stop_loss=price * 95 / 100,
                                reason="örnek")]
        return []

bars = load_bars(["data/synthetic_klines/BTCUSDT-1h-sentetik.csv"], kline_symbols=["BTCUSDT"])
print(format_report(run_backtest(bars, Ornek(), BacktestConfig(slippage_bps=5))))
```

Jev bağlandığında aynı arayüzü uygulayan bir adaptör yazılacak; modelin çıktısı `OrderIntent`'e çevrilip aynı kontrollerden geçecek.

## Doğrulama

- `python -m unittest discover -s tests -t .` → **148 test geçti** (60 mevcut + 88 yeni). Not: mevcut `tests/test_cli.py` testleri depo kökünden çalıştırılmayı varsayıyor; başka klasörden çalıştırılınca 8'i başarısız oluyor (bu PR'dan bağımsız).
- Komisyon, kayma, açılış fiyatı, zarar durdur / kâr al / boşluk, limit emir ve likidite senaryoları elle hesaplanan küçük örneklerle birebir karşılaştırıldı.
- 400 rastgele senaryoda (3.285 gerçekleşme: piyasa, limit, zarar durdur, kâr al) değişmezler kontrol edildi: nakit hiç negatif olmadı; nakit = başlangıç ± işlem akışı; pozisyon = alınan − satılan; **her gerçekleşme fiyatı o barın düşük–yüksek aralığında** (kayma payı dahil); kurallar açıkken her işlem exchangeInfo kurallarına uydu; risk limiti (koruyucu çıkışlar hariç) aşılmadı.
- İndirme aracı ağsız testlerle doğrulandı: SHA-256 uyuşmazlığında, zip'te beklenmeyen dosya adında (ör. `../../evil.csv`) ve okunamayan CSV'de hiçbir dosya yazılmıyor. **Gerçek Binance sunucusuna karşı çalıştırılamadı** (bu ortamda ağ erişimi yok).

Sentetik veride örnek (BTCUSDT, SMA 24/96, kayma 5 bps, örnek kurallar): zarar durdur/kâr al olmadan +29,00% (düşüş %30,36); %4 zarar durdur + %8 kâr al + %1 likidite sınırıyla +3,91% (düşüş %24,19); aynı dönemde al-tut −21,44% (düşüş %61,03). **Veri sentetik olduğu için strateji hakkında bir şey göstermez**, yalnızca motorun çalıştığını gösterir.

## Bilinen sınırlar

- Gerçek veriyle henüz çalıştırılmadı; `data/exchange_info_sample.json` elle yazıldı ve doğrulanmadı.
- Bar içi fiyat sırası bilinmez; aynı barda zarar durdur ve kâr al birlikte değerse zarar durdur varsayılır. Daha ince çözünürlük için daha küçük aralıklı (ör. 1m) veri kullanılabilir.
- Kayma sabit bps; likidite yalnızca "barın hacminin belirli payından büyük emir reddedilir" kuralıyla modelleniyor, fiyat etkisi yok.
- Binance piyasa emrinde NOTIONAL'ı son birkaç dakikanın ortalama fiyatıyla kontrol eder; burada işlem fiyatı kullanılıyor.
- Komisyon USDT'den kesiliyor (Görev 1 varsayımı); BNB indirimi yok.
- Sonuçlar SQLite'a değil CSV/JSON'a yazılıyor; backtest kalıcı hesabı değiştirmez.
- Sharpe gibi yıllıklandırılmış ölçüler eklenmedi.
