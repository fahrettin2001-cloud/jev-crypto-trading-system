# Görev 1 — Sanal işlem çekirdeği: arayüz ve devir notu

Durum: İncelemede — 13 Kasım 2026. Bu not Görev 2'nin (kayıtlar ve kalıcılık) çekirdeği nasıl kullanacağını netleştirmek içindir. Aşağıdaki imzalar öneridir; değişiklik gerekiyorsa PR veya bu not üzerinden konuşalım.

## Görev devri

- Görev ve sorumlu: Görev 1 — @demirfahrieren-png
- Yapılanlar: `jev/` paketi (komisyon, portföy, örnek fiyat okuma), 19 birim testi, örnek senaryo, `pyproject.toml`
- Dosyalar / dal / pull request: `jev/`, `tests/`, `examples/`, `data/sample_prices.csv` — PR #2 (main'e birleşti)
- Çalıştırılan testler ve sonucu: `python -m unittest discover -s tests -t .` → 19 test geçti
- Eksik işler / engeller: kalıcılık yok (Görev 2); PR #2 birleşmeden önce incelenmedi
- Sonraki adım: Görev 2 sorumlusuyla aşağıdaki arayüzün onaylanması

## Veri modelleri (`jev/portfolio.py`)

| Sınıf | Alanlar | Not |
|---|---|---|
| `Position` | `quantity: Decimal`, `avg_cost: Decimal` | `avg_cost` birim başına, komisyon dahil |
| `Trade` (değiştirilemez) | `timestamp: datetime` (UTC), `symbol: str`, `side: "BUY"\|"SELL"`, `quantity`, `price`, `fee`, `realized_pnl` (hepsi `Decimal`) | Satış dışında `realized_pnl = 0` |
| `Portfolio` | `cash: Decimal`, `fees: FeeSchedule`, `quote: str = "USDT"`, `positions: dict[str, Position]`, `trades: list[Trade]`, `initial_cash` | Bellekte tutulur |
| `FeeSchedule` (`jev/fees.py`) | `maker_rate`, `taker_rate` (`Decimal`, varsayılan 0.001) | |

## Metotlar

- `Portfolio.buy(symbol, quantity, price, *, taker=True, timestamp=None) -> Trade`
- `Portfolio.sell(symbol, quantity, price, *, taker=True, timestamp=None) -> Trade`
- `market_value(prices)`, `equity(prices)`, `unrealized_pnl(prices)` — `prices: dict[str, Decimal]`
- `realized_pnl`, `total_fees` — özellik (property)

## Hatalar

- `TradeError` (`ValueError` alt sınıfı): miktar/fiyat ≤ 0, yetersiz nakit, eldekinden fazla satış.
- Reddedilen işlemde portföy **hiç değişmez** (nakit, pozisyon, işlem listesi aynı kalır).
- `KeyError`: değerleme sırasında pozisyonu olan bir sembolün fiyatı yoksa.

## İşlem akışı

1. Girdiler `Decimal`'e çevrilir ve doğrulanır.
2. Tutar = miktar × fiyat; komisyon = tutar × oran (karşı para biriminden).
3. Kontroller geçerse bellek durumu güncellenir ve `Trade` hem döndürülür hem `trades` listesine eklenir.

## Görev 2 için öneri (karar onlarda)

Çekirdek veritabanını bilmez. Kayıt katmanı `buy`/`sell` çağrısını sarıp dönen `Trade` ile güncel `cash` ve `positions` değerlerini tek veritabanı işleminde yazabilir. Veritabanı yazımı başarısız olursa bellekteki portföy de geri alınmalıdır; bunun için çağrıdan önce `copy.deepcopy(portfolio)` almak yeterli bir ilk çözümdür. Yeniden başlatmada portföyü kayıtlardan kurmak için bir `Portfolio.from_state(...)` / `to_state()` ikilisi gerekirse Görev 1 tarafında ekleyebiliriz — ihtiyaç duyulan biçimi bildirin.

## Açık sorular

- Komisyon USDT'den mi alınsın, alınan varlıktan mı (Binance varsayılanı)?
- Örnek komisyon oranı %0,1 kalsın mı?
- `Decimal` değerler SQLite'ta metin (TEXT) olarak mı saklansın? (Kayıpsız olduğu için öneri: evet.)
