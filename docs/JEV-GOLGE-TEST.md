# Jev için işlem yapmayan tahmin ölçümü

`jev.shadow`, geçmişteki fiyat barlarını sırayla tahminciye sunup sonucu
ölçmek için ilk çevrimdışı altyapıdır. Bu sürüm Jev'e bağlanmaz, Binance'e
istek atmaz, emir üretmez ve çalışan sunucu botunu değiştirmez. Tahminci açıkça
çağıran kod tarafından sağlanır; örnek testlerde sahte tahmin kullanılır.

## Ölçülen soru

Belirli bir sembolde, tahmin anındaki kapanış fiyatından `horizon` bar sonraki
kapanış daha yüksek mi? Eşitlik ve düşüş için sonuç `False`; veri sonu nedeniyle
gelecek fiyat yoksa sonuç `None` olur. Her sonuç, zaman, sembol, mevcut fiyat,
ufuk, tahmin olasılığı, sonraki zaman/fiyat ve ölçülen sonucu taşır.

`replay(bars, symbol, horizon, predict)` tahminciye `(gecmis, sembol, ufuk)`
gönderir. Geçmiş tuple olarak sunulur ve tahmin anından sonraki barları içermez.
Bu, dışarıdan başka yollarla geleceği bilen bir tahminciyi veya bir modelin
önceden öğrendiği geçmiş veriyi engellemez. Barlar zaman dilimli, artan ve
sembol bakımından eksiksiz olmalıdır. Geçersiz olasılıklar reddedilir.

`brier_score` yalnızca sonucu belli tahminlerin ortalama karesel olasılık
hatasını hesaplar; sonuç yoksa `None` döner. Düşük puan daha iyidir. Bu puan tek
başına kârlılığı, maliyetleri, riskleri veya bir modelin canlı başarısını göstermez.

## Sonraki çalışma

- Jev API adaptörü için soru, veri sözleşmesi, sürüm ve çağrı maliyeti sınırı
  ayrı tasarlanacak; bu modül henüz API entegrasyonu değildir.
- Gerçekçi değerlendirme için geleceği sızdırmayan ileriye dönük veri ve
  karşılaştırma ölçümleri gerekir. Haber içerikleri ayrıca güvenilmeyen veridir.
- Gerçek veya sanal işlem motoruna bağlamadan önce bağımsız risk kontrolleri,
  hata/eksik veri davranışı ve ekip incelemesi gereklidir.
