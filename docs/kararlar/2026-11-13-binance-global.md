# Karar: Borsa olarak Binance Global

- Tarih: 13 Kasım 2026
- Sorumlu: @demirfahrieren-png (kararı bildiren); ekip onayı bu PR üzerinden
- Durum: Kabul edildi
- Kaynaklar: GOREVLER.md "Açık kararlar", docs/HABER-KAYNAKLARI.md, PR #11 (Binance Global salt okunur adaptörü)

## İhtiyaç

Piyasa verisi, işlem kuralları (lot/fiyat adımı, asgari tutar), haber/duyuru kaynakları ve ileride gerçek emir yolu tek bir borsaya göre tasarlanmalı. GOREVLER.md'de "Binance Global mi Binance TR mi?" açık karar olarak duruyordu.

## Değerlendirilen seçenekler

- **Binance Global (binance.com):** geniş çift ve likidite; belgelenmiş halka açık REST/WebSocket piyasa verisi (`api.binance.com`, `data-api.binance.vision`); PR #11'deki adaptör ve HABER-KAYNAKLARI.md'deki duyuru kaynağı zaten Global'e göre.
- **Binance TR:** TL çiftleri ve yerel düzenleme kapsamı; ayrı API ve kurallar, bu depoda henüz hiçbir şey ona göre yazılmadı.

## Karar ve gerekçesi

Sanal işlem, piyasa verisi ve ileride gerçek emir aşaması Binance Global'e göre tasarlanır. Kote para birimi varsayılanı USDT kalır.

Gerekçe: mevcut çalışmalar (PR #11 adaptörü, haber kaynakları) Global'e göre; halka açık veri herhangi bir hesap gerektirmeden kullanılabilir.

## Etkileri ve takip işleri

- Piyasa verisi: yalnızca halka açık, anahtarsız uç noktalar (mum verisi, `exchangeInfo`, `avgPrice`). Çalışma ortamının ağ izninde `data-api.binance.vision` henüz açık değil (PR #11 notu).
- Sanal işlem gerçekçiliği: Binance Global `exchangeInfo` filtreleri (LOT_SIZE, PRICE_FILTER, NOTIONAL/MIN_NOTIONAL) sanal emirlere uygulanmalı; şu an uygulanmıyor.
- Komisyon: varsayılan %0,1 spot oranı korunur; BNB indirimi ve VIP seviyeleri modellenmez.
- Haber/duyuru: docs/HABER-KAYNAKLARI.md'deki Binance Global duyuru kaynağı geçerli.

## Doğrulanmamış konular

- **Yasal durum:** Türkiye'de yerleşik kullanıcıların Binance Global'de gerçek hesapla işlem yapması SPK düzenlemeleri açısından gerçek emir aşamasından önce ayrıca kontrol edilmeli. 2024 kripto varlık yasasıyla küresel borsaların Türkçe hizmeti kısıtlandı; bu karar hukuki değerlendirme değildir. Sanal işlem ve halka açık veri okuma bu sorudan etkilenmez.
- **Borsa güvenliği:** Binance, 29–30 Ekim 2026'da yaklaşık 6,3 milyar dolarlık bir sıcak cüzdan saldırısı bildirdi, çekimleri geçici olarak durdurdu ve kayıpları kendi fonlarından karşılayacağını açıkladı; çekimler 1 Kasım'dan itibaren aşamalı olarak açıldı. Gerçek para aşamasında borsada tutulacak bakiye sınırı ve çekim politikası bu deneyime göre ayrıca kararlaştırılmalı.
- İlk işlem çiftleri ve sanal bütçe hâlâ açık karar.
