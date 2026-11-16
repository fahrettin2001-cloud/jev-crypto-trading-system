# Geniş tarama — trend kuralları çok sayıda coin ve ABD varlığında (16 Kasım 2026)

Soru: "Yükseliş trendindeki her coinden ya da hisseden küçük bir parça almak" yalnızca BTC+ETH trendinden daha iyi mi? ABD borsasına genişlemek işe yarar mı?

Araç: `python -m jev.genis_tarama` (indir-kripto, indir-abd, test). Tam rapor ve ham veri: sonuç deposunda `veri/genis/` (raporun düzeltilmiş sürümü bu belgede). Ücret harcanmadı: veri Binance arşivinden ve Yahoo'dan (yfinance) ücretsiz alındı, model çağrısı yapılmadı.

## Yöntem

- **Kripto evreni:** 2020 başında piyasa değeri en büyük, Binance'te USDT çifti olan 26 coin. Evren bugün seçilmedi; sonradan gerileyen ya da borsadan çıkarılan coinler de içinde (MATIC, XMR gibi).
- **ETF evreni:** 23 likit ABD ETF'i (endeks, sektör, tahvil, altın, emtia).
- **Hisse evreni:** 2014 sonunun en büyük 30 ABD şirketi (sonradan gerileyenler dahil: GE, IBM, INTC gibi).
- Her varlığa aynı 4 trend kuralı uygulanır. Varyantlar:
  - eşit pay: trenddeki her varlıktan bir parça
  - en iyi K: trenddekilerden son 90 günde en güçlü K varlık
  - genişlik filtresi: trenddeki varlık oranı düşükse hiç yatırım yapma
- Ayar yalnızca eğitim döneminde seçildi (kripto 2020–2023, ETF 2008–2023, hisse 2015-06 → 2023), test dönemi 2024 → Kasım 2026.
- Karar kapanışta verilir, uygulama sonraki işlem gününde. Ağırlıklar fiyatla kayar; hedeften payın %10'undan fazla sapınca masraflı düzeltilir.
- Masraf her ağırlık değişiminde kripto için %0,25, ABD için %0,05.

**Kontrol:**
- Ucuz modelli bağımsız bir alt ajan kodu denetledi. Geleceği görme hatası bulmadı; elle yaptığı hesap motorla birebir tuttu (+%35,1776). Bulduğu üç hata düzeltildi: al-tut'un her gün bedava yeniden dengelenmesi, sıfır momentumun sıralamada en kötü sayılması, boş dönemde çökme.
- İkinci bir alt ajan temel rakamları ayrı bir kodla (pandas) yeniden hesapladı. ETF sonucu tuttu. Kriptoda önce +%114'e karşı +%122 fark çıktı. Sebebi test başlangıç günüydü: alt ajan 2 Ocak'tan, modül 1 Ocak'tan başlıyordu ve aradaki tek gün BTC +%4,5 yükselmişti. Başlangıç günü eşitlenince iki hesap birebir aynı sonucu verdi (+%113,96 / −%32,48 / Sharpe 0,975). Not: tek bir günün toplam getiriyi 8 puan oynatması, toplam getiri rakamlarının kırılgan olduğunu gösteriyor. Karşılaştırmada Sharpe ve düşüşe bakın.

## Sonuçlar — test dönemi (2024 → Kasım 2026, eğitimde hiç kullanılmadı)

### Kripto: daha çok coin daha kötü

| Strateji | Toplam | En büyük düşüş | Sharpe | Masraf |
|---|---|---|---|---|
| BTC+ETH trend (mevcut) | **+%122,0** | **−%32,5** | **1,01** | %6,8 |
| 26 coin, eşit pay (her trenddekinden bir parça) | +%33,0 | −%43,4 | 0,45 | %9,0 |
| Eğitimde seçilen: eşit pay + genişlik ≥ %70 | +%39,0 | −%34,9 | 0,50 | %8,8 |
| En iyi 3 | +%193,0 | −%61,1 | 0,88 | %36,8 |
| Al-tut, 26 coin eşit | +%159,3 | −%53,5 | 0,83 | %0,3 |
| Al-tut, BTC | +%83,0 | −%53,0 | 0,69 | %0,2 |

- Eğitim döneminde de aynı tablo var: BTC+ETH trend Sharpe 1,43, 26 coin eşit pay 1,18.
- Altcoinlerde trend sinyali sık bozuluyor ve masraf artıyor. Sert düşüşlerde de hepsi birlikte çöküyor, yani çeşitlendirme sağlamıyor.
- "En iyi 3" testte yüksek getiri gösterdi, ama eğitimde Sharpe'ı en düşük varyanttı (0,92), düşüşü −%61/−%88 ve masrafı %37–52. Bunu seçmek geçmişe bakarak seçmek olur.

### ABD ETF'leri: getiriyi değil düşüşü azaltıyor

| Strateji | Toplam | En büyük düşüş | Sharpe |
|---|---|---|---|
| Al-tut, SPY | +%63,8 | −%18,8 | 1,18 |
| Al-tut, 23 ETF eşit | +%51,0 | −%12,8 | 1,25 |
| 23 ETF eşit pay trend | +%23,9 | **−%6,9** | 1,12 |
| En iyi 3 / 5 / 8 | +%16–20 | −%16 / −%26 | 0,34–0,57 |

Eğitimde (2008–2023) eşit pay trend Sharpe 0,56, al-tut 0,56. Düşüş ise −%13'e karşı −%42. ETF'lerde trend kâr artırmıyor; aynı Sharpe'ı çok daha küçük düşüşle veriyor. En iyi K varyantları her iki dönemde de kötü.

### ABD hisseleri: kararsız

- Eğitimde seçilen "en iyi 8" testte Sharpe 0,91; al-tut 1,60.
- Eşit pay testte Sharpe 1,76 ve düşüş −%7,8 (al-tut 1,60 ve −%16,3), ama eğitimde al-tuttan kötüydü (0,63'e karşı 0,74).
- Tutarlı bir üstünlük yok. 30 büyük şirketle evren dar; hayatta kalma yanlılığı da tamamen giderilemedi.

### Asıl bulgu: BTC+ETH trend + ETF trend karışımı

Karışım oranı önceden sabitlendi; optimize edilmedi.

| Portföy | Eğitim 2020–2023 (toplam / düşüş / Sharpe) | Test 2024→ (toplam / düşüş / Sharpe) |
|---|---|---|
| BTC+ETH trend %100 | +%950 / −%50,2 / 1,43 | +%122 / −%32,5 / 1,01 |
| **%50 BTC+ETH trend + %50 ETF trend** | +%299 / **−%31,8** / 1,44 | +%73 / **−%16,1** / **1,18** |
| %30 BTC+ETH trend + %70 ETF trend | +%153 / −%23,0 / 1,41 | +%54 / −%10,1 / 1,31 |
| SPY al-tut | +%57 / −%33,7 / 0,61 | +%64 / −%18,8 / 1,21 |

- İki stratejinin günlük getiri korelasyonu yalnızca 0,28–0,32. Kriptonun kötü günleri ETF tarafının kötü günleri değil.
- Karışım her iki dönemde de **düşüşü yaklaşık yarıya indirirken Sharpe'ı korudu ya da artırdı**. Çeşitlendirmenin gerçek faydası budur: aynı risk için daha fazla getiri, ya da aynı getiri için daha az acı.
- Toplam getiri tek başına kriptodan düşük, çünkü sermayenin yarısı daha yavaş büyüyen ETF'lerde.

## Sonuç ve öneri

1. **Coin sayısını artırmayın.** 26 coine yayılmak, BTC+ETH trendinden hem eğitimde hem testte kötü çıktı.
2. **"En iyi K" (en güçlü coinleri kovalamak) yapmayın.** Kripto, ETF ve hisse; üç evrende de yüksek masraf ve büyük düşüş getirdi, sonucu tutarsızdı.
3. **ABD tarafında hisse seçimi değil, ETF trendi.** Getiriyi artırmıyor, ama BTC+ETH trendiyle düşük korelasyonu sayesinde portföyün düşüşünü yarıya indiriyor.
4. **Önerilen sonraki adım:** Üçüncü bir sanal hesapta "%50 BTC+ETH trend + %50 ETF trend" izlensin. ETF'ler hafta içi işlem gördüğü için ayrı bir veri ve zamanlama gerekir; kod yeni bir PR olur. Gerçek para için Türkiye'den ABD ETF erişimi, vergi ve döviz ayrıca araştırılmalı. Bu belge yatırım tavsiyesi değildir.

## Sınırlar

- Test dönemi yaklaşık 3 yıl. Kripto için tek bir döngü; kesin sonuç sayılmamalı.
- Evren seçimi geçmiş tarihe göre yapıldı, ama tamamen yanlılıksız değil (ör. 2020'de var olup Binance'te USDT çifti olmayan coinler yok).
- Karışık portföyde iki yarı arasındaki yeniden dengeleme masrafsız varsayıldı; iki stratejinin kendi masrafları dahil.
- Yahoo verisi temettü ve bölünme düzeltmeli. ETF masrafı (%0,05) aracı kuruma göre değişir.
