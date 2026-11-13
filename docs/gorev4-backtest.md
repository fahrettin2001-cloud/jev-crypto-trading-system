# Görev 4 — Strateji arayüzü, backtest ve Binance işlem kuralları

Durum: İncelemede — 13 Kasım 2026 (@demirfahrieren-png, Claude ile). Ana dala birleşmedi.

## Neden?

Ana dalda işlemleri doğru kaydeden ve risk kurallarını uygulayan bir sanal portföy var; ancak (1) işleme kimin, neye göre karar verdiği tanımlı değildi ve (2) kararların iyi olup olmadığını ölçen bir şey yoktu. Jev / güçlü model bağlanmadan önce aynı hattın basit bir stratejiyle uçtan uca test edilmesi ve sonuçların masraf ve riskle birlikte ölçülmesi gerekiyor (GOREVLER.md "İleriki aşamalar" maddesi).

## Eklenenler

| Dosya | İçerik |
|---|---|
| `jev/strategy.py` | `Bar`, `OrderIntent` (öneri), salt okunur `PortfolioView`, `Strategy` arayüzü; örnek `BuyAndHold` ve `SmaCross` |
| `jev/backtest.py` | Backtest motoru, kayma modeli, metin raporu, `python -m jev.backtest` komutu |
| `jev/metrics.py` | Toplam getiri, en büyük düşüş, kazanan satış oranı, komisyon payı |
| `jev/exchange_rules.py` | Binance Global `exchangeInfo` filtreleri: LOT_SIZE, MARKET_LOT_SIZE, PRICE_FILTER, NOTIONAL/MIN_NOTIONAL |
| `jev/klines.py` | Basit CSV ve data.binance.vision kline CSV'lerinden bar okuma (ms ve µs zaman damgası) |
| `data/exchange_info_sample.json` | **Örnek, doğrulanmamış** exchangeInfo (BTCUSDT, ETHUSDT) |
| `data/synthetic_prices.csv`, `examples/sentetik_veri.py` | **Sentetik** 90 günlük saatlik fiyat; sabit tohumla üretilir |
| `tests/test_strategy.py`, `test_backtest.py`, `test_exchange_rules.py` | 53 yeni test |

Mevcut modüller (`portfolio`, `fees`, `risk`, `storage`, `__main__`) değiştirilmedi; açık PR #10 ve #11 ile dosya çakışması yok.

## Akış

```
Bar kapanır → strateji PortfolioView + Bar görür → OrderIntent listesi
  → (sonraki bar) fiyat + kayma → miktar işlem adımına aşağı yuvarlanır
  → Binance kuralı kontrolü → RiskLimits.check → deneme portföyünde alış/satış
  → RiskLimits.check_after_buy → geçerse kabul, geçmezse Rejection kaydı
  → portföy son bilinen fiyatlarla değerlenir → varlık eğrisi
```

Önemli tasarım kararları:

- **Geleceği görme yok:** Strateji barın kapanışını gördükten sonra karar verir; öneri bir sonraki barın fiyatıyla gerçekleşir. `--same-bar` yalnızca farkı görmek için.
- **Strateji portföyü değiştiremez:** Yalnızca salt okunur görünüm alır. İleride Jev aynı arayüze bağlanacak; modelin çıktısı doğrudan işlem değil, kontrol edilecek bir öneridir.
- **Reddedilen öneriler kaybolmaz:** Her red nedeniyle kaydedilir (risk, işlem kuralı, nakit yetersizliği, veri sonu).
- **Mevcut risk katmanı kullanılır:** `RiskLimits` aynen uygulanır; alış sonrası kontroller kopya üzerinde, geçmezse portföy değişmez.

## Kullanım

```bash
# Sentetik veriyle SMA kesişimi, al-tut kıyasıyla
python -m jev.backtest --prices data/synthetic_prices.csv \
    --rules data/exchange_info_sample.json --fast 24 --slow 96

# Gerçek Binance verisiyle (data.binance.vision'dan indirilen aylık dosyalar)
python -m jev.backtest --prices BTCUSDT-1h-2026-09.csv BTCUSDT-1h-2026-10.csv \
    --kline-symbols BTCUSDT BTCUSDT --rules data/exchange_info.json

# Örnek risk limitiyle
python -m jev.backtest --prices data/synthetic_prices.csv --max-trade-notional 5000
```

Diğer seçenekler: `--strategy al-tut`, `--symbol`, `--fraction`, `--cash`, `--taker-rate`, `--slippage-bps` (varsayılan 5). `python -m jev.backtest -h`.

Python'dan:

```python
from jev.backtest import BacktestConfig, run_backtest, format_report
from jev.klines import load_bars
from jev.strategy import SmaCross

bars = load_bars(["data/synthetic_prices.csv"])
result = run_backtest(bars, SmaCross("BTCUSDT", 24, 96), BacktestConfig(slippage_bps=5))
print(format_report(result))
```

Yeni strateji yazmak için `name` niteliği ve `on_bar(bar, view)` metodu olan, `OrderIntent` listesi döndüren bir sınıf yeterli.

## Doğrulama

- `python -m unittest discover -s tests -t .` → 113 test geçti (60 mevcut + 53 yeni).
- Komisyon ve kayma hesapları elle hesaplanan küçük senaryolarla birebir karşılaştırıldı (`test_fees_and_slippage_exact`, `test_round_trip_metrics`).
- Sentetik veride örnek çıktı (SMA 24/96, kayma 5 bps, örnek kurallar): +15,96% getiri, en büyük düşüş %14,90, 18 işlem; aynı dönemde BTC al-tut +9,84%, en büyük düşüş %41,91. **Sentetik veriyle elde edildiği için stratejinin işe yaradığına dair kanıt değildir**; yalnızca motorun çalıştığını gösterir.

## Bilinen sınırlar ve sonraki adımlar

- **Gerçek veri yok:** Çalışma ortamının Binance'e ağ erişimi yok (403). `data/exchange_info_sample.json` elle yazıldı ve doğrulanmadı; gerçek `exchangeInfo` cevabı ve data.binance.vision kline dosyaları indirilince aynı kodla kullanılabilir.
- Yalnızca kapanış fiyatı kullanılıyor; stop-loss / take-profit ve limit emir (bar içi yüksek/düşük gerektirir) yok.
- Kayma sabit bps; emir büyüklüğüne veya likiditeye göre değişmiyor.
- Binance piyasa emrinde NOTIONAL'ı ortalama fiyatla kontrol eder; burada işlem fiyatı kullanılıyor.
- Komisyon USDT'den kesiliyor (Görev 1 varsayımı); BNB indirimi yok.
- Sonuçlar SQLite'a yazılmıyor; backtest bellekte çalışır. İstenirse `SQLitePortfolio` ile canlı-sanal mod ayrıca bağlanabilir.
- Sharpe gibi yıllıklandırılmış ölçüler eklenmedi; kısa ve sentetik veride yanıltıcı olur.
- Jev / Hermes bağlantısı: `Strategy` arayüzüne uyan bir adaptör yazılacak; model çıktısı `OrderIntent`'e çevrilip aynı kontrollerden geçecek.
