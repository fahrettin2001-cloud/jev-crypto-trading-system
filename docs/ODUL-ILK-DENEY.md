# Görev 6: sentetik ödül hesabı

`experiments/reward_demo.py` yalnızca örnek ve çevrimdışı bir hesaplayıcıdır.
Botun sanal veya gerçek işlemlerine bağlanmaz, API çağırmaz, model ağırlıklarını
değiştirmez. Sinir ağı deneyiyle aynı araştırmanın ayrı bir parçasıdır.

## Ölçüm sözleşmesi

İki değer aynı para birimindeki, pozisyonların güncel değeri dahil **net toplam
portföy değerleridir**. Kapsamları aynı, zamanları ardışık ve aralarında para
yatırma/çekme olmamalıdır. Kaynak portföy değerlerinin işlem komisyonlarını ve
gerçekleşen kaymayı zaten yansıttığı varsayılır; ayrı bildirilen dönem komisyonu
yalnızca bilgilendirme içindir, ikinci kez düşülmez. Girdi kaynağının bu
varsayımları gerçekten karşılaması entegrasyon öncesinde doğrulanmalıdır.

- Net getiri = (sonraki değer - önceki değer) / önceki değer.
- Önceki tepe daha önce gözlenmiş en yüksek portföy değeridir ve önceki
  değerden küçük olamaz; yeni tepe gerekirse sonraki değere yükseltilir.
- Düşüş = (tepe - değer) / tepe.
- Örnek risk cezası = seçilen katsayı × düşüşteki pozitif artış. Katsayı
  varsayılan olarak **0**'dır; onaylı bir risk parametresi değildir.
- Ödül = net getiri - örnek risk cezası. Bu bir araştırma formülüdür.

Örnek: net değer 500'den 502'ye çıkarsa getiri ve sıfır risk cezasıyla ödül
0,004'tür (%0,4). 0,2 komisyon değere zaten yansıdıysa ayrıca çıkarılmaz.
Tepe 500, sonraki değer 450 ve örnek risk katsayısı 0,5 ise getiri -0,10,
düşüş artışı 0,10, ceza 0,05 ve ödül -0,15'tir. Bunlar yatırım hedefleri değil,
hesabın açıklanması için sentetik sayılardır.

## Çalıştırma ve kayıt

```bash
python experiments/reward_demo.py
python -m unittest tests.test_reward_demo
```

`reward_record` açıkça verilen sayılardan sonuç sözlüğü üretir; `append_record`
ancak çağıran dosya yolu verirse JSONL satırı ekler. Varsayılan otomatik kayıt
yoktur. API anahtarları, kişisel veya gerçek işlem verileri depoya eklenmez.

Gelecekte sinir ağına ödülden öğrenme bağlanacaksa eğitim süreci, örnek
bağlantıları, veri bölmeleri, masraf ve kısıtlar ayrı tasarlanıp sınanmalıdır.
Bu hesaplayıcının varlığı Jev'i veya sinir ağını kendiliğinden eğitmez.
