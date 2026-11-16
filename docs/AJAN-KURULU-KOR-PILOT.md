# Ajan kurulu: ilk anonim tahmin provası — 16 Kasım 2026

## Hedef ve kapsam

Üç ücretsiz alt ajan, Jev'e bağlı bir yatırımcı eğitim sisteminin ön çalışması
olarak boğa, ayı ve risk analisti rolünde bağımsız tahminler verdi. Her ajana
aynı üç anonim durum, her durumda iki anonim varlığın 7/30/90 günlük getirisi,
50 günlük ortalamaya uzaklığı, 30 günlük oynaklığı ve 90 günlük zirveden düşüşü
gösterildi. Soru, 20 gün sonraki kapanışın daha yüksek olup olmadığıydı.
Haber, emir, ücretli model veya Jev çağrısı kullanılmadı.

Bu **yatırım simülasyonu veya ağ eğitimi değildir**. Her rol öznel olasılık verdi;
birleştirme basit eşit ağırlıklı ortalamadır. Tahminler sonuçlar açılmadan önce
`0aa64884868221f274817261f27976869fb41f72` commit'inde kaydedildi. Ajanlara
araç/dosya/ağ kullanmamaları söylendi ancak ortak çalışma alanı teknik olarak
yalıtılmadı. Dosyaların veya internetin erişilemez olduğu kanıtlanmadı. Fiyat
şekli ve ön eğitim bilgisi de dönemi ima edebilir; tarihsel deney kesin körlük
sağlamaz. Ajanlar birbirinden yalıtılmış bağımsız modeller olarak varsayılamaz.

## Ham sonuç

Veri: `demirfahrieren-png/jev-canli-sonuclar` commit `726a3ed5591774bf8c506c4cd240efaad3220800`,
`veri/genis/kripto/` günlük kapanışları. BTC SHA-256
`2ab03c193763b11455cfc6fb8248e5d6dfc0611622d92537570d3fd67659b5f4`, ETH
`f2751d61b1dd0ecbb662bdb171fbacc37b10bccb6864fb581d97a1753d21e808`.
Örnekler 1 Temmuz 2022, 1 Eylül 2023 ve 1 Eylül 2024: her birinde BTC ve ETH.
Rastgele seçilmiş veya bağımsız nihai sınav değildir; dönemler daha önce incelendi.

| Örnek | Ajan ortalaması | 20 gün sonra | Yön |
|---|---:|---:|---|
| 1A BTC | 0,477 | +%20,09 | yukarı |
| 1B ETH | 0,460 | +%48,67 | yukarı |
| 2A BTC | 0,483 | +%2,96 | yukarı |
| 2B ETH | 0,477 | -%2,77 | aşağı |
| 3A BTC | 0,473 | +%10,55 | yukarı |
| 3B ETH | 0,457 | +%7,70 | yukarı |

Altı örneğin ortalama Brier puanı ajan ortalamasında **0,2720**, sürekli %50
tahmininde **0,2500**. Düşük daha iyidir. Altı örnek ve bir kez denenmiş
öznel görüşlerle başarı, başarısızlık, yatırım getirisi veya model gücü hakkında
genelleme yapılamaz. BTC/ETH ve aynı gündeki örnekler bağımsız da değildir.

## Tekrarlama

`python -m experiments.ajan_kurulu_pilot.puanla --data <veri/genis/kripto>`

Puanlayıcı eksik/tekrarlı kimlikleri, mantık değerlerini, sonlu olmayan veya
aralık dışı olasılıkları ve eksik/tekrarlı günleri reddeder. Kaynak dosyalar ve
öngörü kayıtları GitHub'da sabitlenir; veri SHA-256 değerleri raporlanır.

## Sonraki aşama

İlk olarak yatırımcı ve uzmanlara yalnızca karar anına kadar olan gözlemleri
gösteren, ağ erişimi ve dosya erişimi teknik olarak sınırlandırılmış ayrı bir
ortam gerekir. Hakem geleceği ayrı tutmalı; her karar değişmez biçimde kayda
geçtikten sonra yalnızca vadesi gelmiş sonuçları göstermelidir. Verinin ön eğitim
hafızası da dikkate alınmalı ve ileriye dönük gölge gözlem yapılmalıdır.
Gerçek piyasa verisi, alış/satış komisyonu, kayma, risk limitleri, işlem yapmama
seçeneği ve basit kıyaslar birlikte ölçülmeden yatırımcı başarısı iddia edilemez.
Jev için bu yerel ortamda anahtar ve SDK yoktu; hiçbir ücretli istek yapılmadı.
