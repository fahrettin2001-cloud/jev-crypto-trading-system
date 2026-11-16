# Trend topluluğu — ikinci sanal hesap

Durum: Kod, testler ve sunucu kurulumu hazır (16 Kasım 2026). Mevcut canlı sanal bot (SMA 24/96, saatlik) kıyas için olduğu gibi çalışmaya devam eder.

## Neden?

- Saatlik SMA 24/96 stratejisi sağlamlık testinde masraflar düşülünce zarar etti (`docs/saglamlik-2026-11.md`).
- 16 Kasım araştırmasında yavaş, günlük trend kuralları masraflara dayanıklı çıktı.
- Kurallar 2024-11 → 2026-10 verisine bakılarak seçildi. Bu yüzden kurallar için hiç görülmemiş 2018–2023 döneminde de test edildi: Sharpe **1,10**. 2018–2026'nın tamamında trend Sharpe 1,07 ve en büyük düşüş −%49; eşit ağırlıklı al-tutta 0,59 ve −%84 (`docs/DUYGU-ENDEKSI.md`, geçmiş testi).

## Strateji

Her coin için 4 kuralın ortalaması alınır; hedef ağırlık 0, ¼, ½, ¾ ya da 1 olur:

1. SMA10 > SMA40
2. SMA20 > SMA100 (±%1 bant; bant içinde önceki durum korunur)
3. Fiyat > SMA50
4. Fiyat > SMA100 (±%2 bant)

Hedef pozisyon = toplam varlık × coin payı × ağırlık. Ağırlık 0'a düşerse coinin tamamı satılır. Pozisyon hedeften payın %10'undan fazla saparsa fark kadar alınır ya da satılır; küçük sapmalar için işlem yapılmaz. Karar günlük mum kapanışında verilir, işlem bir sonraki günün açılışında yapılır.

Uygulama: `jev/strategy.py` (`TrendRules`, `TrendTopluluk`). Ağırlıklar araştırmadaki hesapla (`jev.duygu.trend_weights`) birebir aynıdır; bunu bir test denetler.

## Canlı sanal ayar

| Ayar | Değer |
|---|---|
| Bütçe | 500 USDT (sanal) |
| Coinler | BTCUSDT, ETHUSDT |
| Coin payı | %30 (`--fraction 0.6`); trend tam açıkken varlığın %60'ı yatırımda |
| Risk limitleri ("temkinli") | işlem başına 50, coin başına 150, nakitte en az 200 USDT |
| Mum | günlük (`--interval 1d`), 100 gün ısınma |
| Masraf | komisyon %0,1, kayma 5 bps, Binance işlem kuralları |

Strateji risk limitlerini bilir: hedefi coin başına sınıra ve nakit rezervine göre kırpar, alımları 50 USDT'lik dilimlere böler. Böylece öneriler her gün reddedilmez.

**Beklenti** (gerçek Binance verisi, 2024-11 → 2026-10, bu ayarlarla simülatörde): +%25,8 getiri, en büyük düşüş −%15,2, iki yılda 112 işlem, 4,52 USDT komisyon, 0 red. Aynı dönemde eski canlı ayar (SMA 24/96) −%4,9 getirmişti. Geçmiş sonuç gelecekteki getiriyi göstermez. Günlük strateji ayda birkaç işlem yapar; bu yüzden birkaç haftalık canlı sanal sonuç kârlılığı kanıtlamaz, yalnızca botun doğru çalıştığını gösterir.

Simülatör doğrulaması: limitsiz ayarda motor +%50,4 / −%27,7 verdi; araştırmanın kapanıştan kapanışa hesabı +%50,7 / −%27,2. Küçük fark, işlemlerin ertesi gün açılışında yapılmasından ve Binance miktar kurallarından geliyor.

## Kurulum (sunucu, root)

```bash
cd /opt/jev/app && sudo -u jev git pull && bash deploy/install-trend.sh
```

- Hesap `/var/lib/jev/trend` klasöründe tutulur. `jev-trend.timer` her gün 00:05 UTC'de (03:05 TR) çalışır; 06:05 UTC'de bir yedek deneme daha yapar.
- Sonuçlar `jev-sonuc` ile sonuç deposunun `son/trend/` klasörüne yayınlanır.
- Durum: `sudo -u jev python3 -m jev.live status --dir /var/lib/jev/trend --horizon 5`
- Acil durdurma: `touch /var/lib/jev/trend/DURDUR`
- Kapatmak: `systemctl disable --now jev-trend.timer`

Henüz yapılmadı: bu klasör için günlük şifreli yedek (`jev-backup` yalnızca `/var/lib/jev/canli` klasörünü yedekliyor).
