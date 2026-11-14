# Görev 6 — Yapay sinir ağı ve ödül sistemi araştırması

Durum: Planlandı; geliştirme ve eğitim bu görev kapsamında henüz yapılmadı. Sorumlu: fahrettin2001-cloud ve bu çalışma alanındaki ajan. Takip: [GitHub görevi #29](https://github.com/fahrettin2001-cloud/jev-crypto-trading-system/issues/29). Çalışma Demir'in Görev 5'iyle koordine edilir.

## Fikir ve kavramlar

Proje sahibinin isteği, eğitim sırasında sonuçlara göre değişebilen ayrı bir küçük yapay sinir ağı ve performans için sayısal ödül sistemi araştırmaktır. Ağırlık güncellemeleri ile yalnızca skor/rapor hesaplama farklı işlerdir. Ödül, duygu veya otomatik öğrenme değildir. Paylaşılan görseldeki iki sınıflı örnek, etiketli veriden öğrenen basit bir ağdır; işlem kârıyla pekiştirmeli öğrenme değildir. Örneğin sentetik veri başarısı kripto piyasasına taşınamaz.

## Tasarlanan ilişkiler

- Jev: sunulan durum ve sorulara yapılandırılmış yanıt üreten dış servis. Geri bildirim göndermek Jev'in ağırlıklarını kendiliğinden değiştirmez.
- Ayrı sinir ağı: girdileri ve hedefi belirlendikten sonra ayrı süreçte eğitilecek aday model; henüz yok.
- Ana ajan: ileride mevcut raporları, model çıktılarını ve kaynakları değerlendirecek bileşen; henüz bu yapıya bağlı değil.
- Risk ve sanal işlem katmanı: öğrenme deneyinden bağımsız kalır. Çalışan Hostinger sisteminde değişiklik yapılmaz.

## Aşamalar

1. Sentetik noktalarla küçük eğitim deneyi: tekrarlanabilir başlangıç, eğitim ve bağımsız test veri kümeleri, basit karşılaştırma ve yanlış örneklerin raporu.
2. Geçmiş piyasa verisi üzerinde ancak tasarımı gözden geçirildikten sonra: özelliklerin tahmin anında mevcut olması, zaman sıralı eğitim/doğrulama/test, geleceğe bakma ve dönem çakışması denetimi, basit başlangıç yöntemleriyle karşılaştırma.
3. Sanal portföyde hesaplanan sonuçları kayıt altına alma: gerçekleşen/gerçekleşmemiş portföy değişimi, ücretler, kayma, oynaklık ve düşüş ayrı saklanır. Ücretler portföy değerine zaten yansımışsa ikinci kez düşülmez. Ödül işlevi, ufuk ve risk cezaları örneklerle ayrıca kararlaştırılır.
4. Ayrı deneylerde eğitim/yeniden eğitim, veri kaynağı ve model sürümü kayıtları; görülmemiş dönemler ve ileriye dönük gölge deneme. Geçmiş veriler modelin önceden bildiği bilgileri içerebilir.
5. Olası entegrasyon, bağımsız risk kontrolleri ve ekip incelemesinden sonra ayrı görevle değerlendirilir; bu belge işlem açma yetkisi vermez.

PR #27, henüz tamamlanmamış gölge tahmin değerlendirmesine başlangıçtır; sinir ağı veya Jev entegrasyonu olduğunu iddia etmez. API anahtarları, hesap bilgileri ve ham işlem kayıtları halka açık GitHub'a yazılmaz.

## Bitti ölçütü

Sentetik eğitim ve eğitim dışı testler tekrarlanabilir olmalı; sızıntı sınamaları, maliyet/risk hesap örnekleri ve tahmin doğruluğunun kârla aynı şey olmadığı açıklanmalıdır. Öğrenen bileşen ile yalnızca rapor üreten bileşen açıkça ayrılır. Hiçbir sonuç gelecekte kâr garantisi olarak sunulmaz.
