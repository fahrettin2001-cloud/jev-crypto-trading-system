# Görev 6: ilk sentetik sinir ağı deneyi

Bu küçük eğitim örneği iki sayının işaretlerinin aynı olup olmadığını öğrenir.
Veriler yapay olarak üretilir: **kripto fiyatı, yatırım kararı ve gerçek para
içermez**. Amaç nöron, ağırlık ve eğitim fikrini anlaşılır hale getirmektir.

## Çalıştırma

Python 3.10+ ile proje kökünde:

```bash
python experiments/neural_demo.py
python -m unittest tests.test_neural_demo
```

Deney Python standart kütüphanesini kullanır; ağ erişimi ve API anahtarı
gerektirmez. Varsayılan koşulda 800 yapay eğitim ve ayrı üretilen 400 test
noktası vardır. 2 girdi, 8 ReLU nöronu, 1 olasılık çıktısı ve ikili çapraz
entropi üzerinden elle yazılmış geri yayılım kullanılır. Eğitim tekrarlanabilir
tohumlarla 1.500 küçük veri grubu adımı sürer.

## Doğrulama ve anlamı

13 Kasım 2026'da sınırlı Python 3.13 ortamında deney doğrudan çalıştırıldı:
eğitim öncesi %31, eğitim sonrası %97,75 ve eğitim kümesindeki çoğunluk sınıfına
dayalı karşılaştırma %49,5. Ayrıca aynı tohumla tekrarlanabilirlik, etiketler,
başarım artışı ve boş veri reddi elle denendi. Bulut ortamında Python 3.12.14 ile ilgili 7 test ve toplam 207 test geçti.
Mevcut `test_backtest_orders.py` içindeki iki açık CSV dosyası için
`ResourceWarning` görüldü; testler başarısız olmadı. Bu sayılar yalnızca kolay, üretilmiş bir sınıflandırma
probleminin sonuçlarıdır; kripto tahmini, getiri veya kârlılık göstermez.

Bu örnek denetimli öğrenmedir: doğru etiketleri biliyoruz. İşlem sonucunu ödül
sinyali olarak kullanan pekiştirmeli öğrenme değildir. Model Jev'e, 500 USDT'lik
sanal bota veya risk katmanına bağlanmaz; ağ ağırlıkları dosyaya kaydedilmez.
Gerçek piyasa araştırması için zaman sıralı veri, sızıntı kontrolleri, ayrı
eğitim/doğrulama/test dönemleri, maliyetler ve temel yöntemlerle kıyas gerekir.
TypeSafe çıktılarını başka modeli taklit etmek üzere eğitimde kullanmadan önce
hesaba uygulanan sözleşme ayrıca incelenmelidir.
