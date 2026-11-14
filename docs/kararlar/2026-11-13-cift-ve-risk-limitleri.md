# Karar önerisi: İşlem çiftleri ve risk limitleri

- Tarih: 13 Kasım 2026
- Öneren: @demirfahrieren-png
- Durum: Önerildi — ekip onayı bekliyor (bu PR üzerinden). Sanal bütçe henüz seçilmedi.
- Kaynaklar: GOREVLER.md "Açık kararlar", `docs/kararlar/2026-11-13-binance-global.md`, `docs/gorev4-backtest.md`

## İhtiyaç

Jev'i strateji arayüzüne bağlamadan önce sistemin hangi çiftlerde işlem yapacağı ve hangi sınırları asla aşmayacağı belli olmalı. Jev ne önerirse önersin risk limitleri bağımsız olarak uygulanır.

## Öneri

### İşlem çiftleri

**BTCUSDT ve ETHUSDT** (Binance Global spot). Gerekçe: en yüksek likiditeye sahip iki çift; kayma düşük olduğu için backtest sonuçları gerçeğe daha yakın; gerçek exchangeInfo kuralları depoda hazır (`data/exchange_info_sample.json`).

### Risk limitleri — "temkinli" paket

Yüzdeler başlangıç sanal bütçesine göredir; bütçe seçilince USDT tutarlarına çevrilir.

| Kural | Değer | Karşılık gelen ayar |
|---|---|---|
| İşlem başına azami tutar | Bütçenin %10'u | `max_trade_notional` |
| Tek coinde azami pozisyon değeri | Bütçenin %30'u | `max_position_notional` |
| Her zaman nakitte kalacak asgari tutar | Bütçenin %40'ı | `min_cash_reserve` |
| Günlük gerçekleşen zarar sınırı | Bütçenin %2'si (aşılınca o gün yeni alış yok) | `max_daily_realized_loss` (PR #11) |
| İzin verilen semboller | BTCUSDT, ETHUSDT | `allowed_symbols` |

Örnek: bütçe 10.000 USDT seçilirse işlem başına 1.000, tek coinde 3.000, nakitte en az 4.000, günlük zarar sınırı 200 USDT.

Değerlendirilen diğer paket ("dengeli"): işlem başına %20, tek coinde %50, nakitte %20, günlük zarar %4. Sanal aşamada daha sıkı sınırlarla başlayıp sonuçlara göre gevşetmek, tersinden daha güvenli olduğu için temkinli paket önerildi.

## Açık kalanlar

- **Sanal bütçe:** ekiple konuşulacak (1.000 / 10.000 / 100.000 USDT seçenekleri değerlendirildi).
- Günlük zarar sınırı PR #11 birleşince kullanılabilir; gün sınırı şu an UTC'ye göre.
- Fiyat yaşı sınırı (`max_price_age`) ve toplam pozisyon sınırı ayrıca belirlenmeli.
- Bu değerler yalnızca sanal aşama içindir; gerçek paraya geçmeden önce yeniden değerlendirilmeli.
