# Duygu endeksi — bedava piyasa duygusu ölçümü

Durum: Kod ve testler hazır (16 Kasım 2026). Geçmiş testi sunucuda çalıştırılacak; sonucuna göre filtre olarak kullanılıp kullanılmayacağına karar verilecek.

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

## Kurulum (sunucu, root)

```bash
cd /opt/jev/app && sudo -u jev git pull && bash deploy/install-duygu.sh
```

Betik geçmiş veriyi indirir, geçmiş testini `/var/lib/jev/duygu/gecmis_testi.md` dosyasına yazar ve günlük kaydı açar (`jev-duygu.timer`, 00:15 UTC). Yalnızca standart kütüphane kullanılır; ek paket, anahtar ya da ücret gerekmez. Sonuçlar `jev-sonuc` ile sonuç deposunun `son/duygu/` klasörüne yayınlanır.

Komutlar: `python -m jev.duygu indir | test | gunluk --dir <klasör>`.

## Sınırlar

Emir yok; canlı sanal bot, ajan kurulu ve risk katmanı değişmez. Geçmiş testi iyi çıksa bile filtre önce gölge modda izlenmeli, sonra ayrı bir PR ile stratejiye eklenmelidir. Geçmiş sonuç gelecekteki getiriyi göstermez.
