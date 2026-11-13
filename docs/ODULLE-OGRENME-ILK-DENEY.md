# Görev 6: ödülle öğrenme — sentetik ilk deney

Bu deney küçük bir sinir ağının ağırlıklarını **ödül sinyaliyle gerçekten
günceller**. Görev: iki rastgele sayının işaretleri aynıysa 1, farklıysa 0
eylemini seçmek. Yapay ortam doğru eylem için +1, yanlış eylem için -1 verir;
öğrenme kodu doğru etiketi değil seçilen eylemin ödülünü alır. Tek adımlı,
gürültüsüz bir oyuncak örnektir; piyasa veya alım satım simülasyonu değildir.

## Yapı

- Ağ: 2 girdi, 8 ReLU nöronu, eylem 1 için sigmoid olasılığı.
- Eğitim: 20.000 sentetik etkileşimde olasılığa göre rastgele eylem; REINFORCE
  ile `ödül × (seçilen eylem - olasılık)` yönünde ağırlık güncellemesi.
- Test: eğitimden ayrı rastgele tohumla üretilen 2.000 nokta; ağırlıklar
  dondurulur ve olasılık eşiği 0,5 olarak kullanılır. Her zaman rastgele eylem
  seçmenin beklenen tabanı %50'dir.
- Testler: olumlu/olumsuz ödülün seçilen eylem olasılığını uygun yönde
  değiştirmesi, sıfır ödülde ağırlıkların değişmemesi, geçersiz değerlerin
  reddi ve farklı başlangıçlarda bağımsız sentetik noktalarda başarı.

Çalıştırma:

```bash
python -m experiments.reward_learning
python -m unittest tests.test_reward_learning
```

## İlk bulgular ve sınırlar

13 Kasım 2026'da örnek yapılandırmada eğitim öncesi %27,8; ayrı üretilen test
noktalarında eğitim sonrası %97,2 doğruluk ölçüldü. Ayrıca 10 farklı eğitim
başlangıcı ve ayrı test kümesinde doğruluk aralığı %95,4–%98,9 oldu. Bu
değerler yalnızca sentetik kurala aittir; gerçek kripto tahmini, para kazanma,
gelecekteki performans veya risk kontrolü hakkında kanıt değildir.

Bu modül `experiments/reward_demo.py` içindeki portföy ödül hesabını kullanmaz;
orada kullanılan gerçekçi muhasebe varsayımları bu deneyde test edilmemiştir.
Jev çıktılarını kullanmaz, Jev modelini eğitmez, Hostinger'a erişmez ve emir
üretmez. Gerçek dünya veya sanal işlem entegrasyonu farklı bir aşamadır ve bu
deneyin başarısı tek başına ona geçiş gerekçesi değildir.
