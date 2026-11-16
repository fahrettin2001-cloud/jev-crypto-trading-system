# Duygu endeksi — bedava piyasa duygusu ölçümü

Durum: Geçmiş testi 16 Kasım 2026'da sunucuda çalıştırıldı. **Sonuç: duygu filtresi stratejiye eklenmiyor.** Endeks yalnızca bilgi amaçlı günlük kaydediliyor.

## Neden?

TradingAgents'ın duygu analisti Reddit ve StockTwits okuyordu. Bu siteler Hostinger'ın veri merkezi IP'sinden 403 veriyor. Reddit ayrıca yeni API erişim taleplerini 31 Ekim 2026'da kapattı ve kalan erişimi Mart 2027'de sonlandıracak. Ücretli sosyal medya verisi yerine, anahtarsız ve model çağrısı yapmayan sayısal kaynaklar kullanıyoruz:

| Kaynak | Ne ölçer | Geçmiş |
|---|---|---|
| Korku ve Açgözlülük Endeksi (alternative.me) | Piyasanın genel ruh hâli, 0–100 | 2018-02'den beri günlük |
| Binance vadeli fonlama oranı | Kaldıraçlı alıcıların kalabalığı; yüksekse herkes aynı yöne yüklenmiş demektir | BTCUSDT 2019-09'dan beri |
| Binance long/short hesap oranı | Yükselişe ve düşüşe oynayan hesapların oranı | Yalnızca son 30 gün; bu yüzden her gün kaydedilir |

alternative.me verisi, kaynak belirtildiği sürece ticari kullanım dahil serbesttir. Raporlarda "Veri: alternative.me" yazılır.

## En iyi kullanım: trend stratejisine filtre

Bu göstergeler tek başına kâr sinyali değildir. Genelde ters yönlü ve yalnızca uç değerlerde işe yarar. Bu yüzden 16 Kasım araştırmasında bulunan **yavaş trend topluluğuna** filtre olarak denenir. Topluluk 4 kuralın ortalamasıdır: SMA10>SMA40, SMA20>SMA100 (±%1 bant), fiyat>SMA50 ve fiyat>SMA100 (±%2 bant).

- **Açgözlülük filtresi:** endeks ≥ G iken pozisyon yarıya iner.
- **Korku filtresi:** endeks ≤ F iken trend kapalı olsa bile en az %50 pozisyon alınır (ters yönlü alım).
- **Fonlama filtresi:** 7 günlük ortalama fonlama yıllık H'nin üstündeyse pozisyon yarıya iner.

## Geçmiş testi kuralları

- Ayarlar yalnızca **eğitim döneminde** (2018-02 → 2023-12) seçilir. Ardından hiç kullanılmamış **test döneminde** (2024-01 → bugün) tek seferde ölçülür.
- Karar gün kapanışında verilir, ertesi gün uygulanır. Her ağırlık değişiminde %0,15 masraf (komisyon %0,1 + kayma 5 bps) düşülür.
- Rapor, bütün ızgaranın test sonuçlarını da gösterir. Filtrelerin çoğu test döneminde trendi geçemiyorsa, seçilen filtrenin başarısı tesadüf sayılır.
- Kıyas: eşit ağırlıklı al-tut ve filtresiz trend topluluğu.

## Geçmiş testi sonucu — 16 Kasım 2026

Veri: 2018-02 → 2026-11-15, BTCUSDT+ETHUSDT. Fonlama verisi BTC için 2019-09-10'dan, ETH için 2019-11-27'den başlıyor.

| Test dönemi (2024-01 → 2026-11) | Toplam | Yıllık | En büyük düşüş | Sharpe |
|---|---|---|---|---|
| Al-tut | +%17,5 | +%5,8 | −%59,9 | 0,37 |
| Trend topluluğu | +%122,5 | +%32,1 | −%31,6 | 1,01 |
| Trend + eğitimde seçilen filtre (korku≤20 → en az %50) | +%129,3 | +%33,4 | −%33,3 | 1,00 |

- Eğitimde seçilen filtre, test döneminde Sharpe'ı iyileştirmedi (1,01 → 1,00) ve düşüşü büyüttü. 19 filtrenin 10'u trendi geçti; bu yazı-tura düzeyinde, gerçek bir etki yok. Fonlama ve açgözlülük filtreleri eğitimde de trendden kötüydü.
- **Yan bulgu:** Trend topluluğunun kuralları 2024-11 → 2026-10 verisine bakılarak seçilmişti. 2018–2023 eğitim dönemi bu kurallar için hiç görülmemiş veri sayılır ve orada Sharpe **1,10** çıktı. 2018–2026 tüm dönemde trend Sharpe 1,07 ve en büyük düşüş −%49; al-tutta bunlar 0,59 ve −%84. Bu sonuç, trend topluluğunun canlı sanal hesapta denenmesine dayanak oldu.

## Kurulum (sunucu, root)

```bash
cd /opt/jev/app && sudo -u jev git pull && bash deploy/install-duygu.sh
```

Bilgi amaçlı günlük kayıt içindir. Betik geçmiş veriyi indirir, geçmiş testini `/var/lib/jev/duygu/gecmis_testi.md` dosyasına yazar ve günlük kaydı açar (`jev-duygu.timer`, 00:15 UTC). Yalnızca standart kütüphane kullanılır; ek paket, anahtar ya da ücret gerekmez. Sonuçlar `jev-sonuc` ile sonuç deposunun `son/duygu/` klasörüne yayınlanır.

Komutlar: `python -m jev.duygu indir | test | gunluk --dir <klasör>`.

## Sınırlar

Emir yok; canlı sanal bot, ajan kurulu ve risk katmanı değişmez. Geçmiş testi iyi çıksa bile filtre önce gölge modda izlenmeli, sonra ayrı bir PR ile stratejiye eklenmelidir. Geçmiş sonuç gelecekteki getiriyi göstermez.
