# Sinyal laboratuvarı — grafikte nelere bakılmalı? (16 Kasım 2026)

Amaç: ajana "grafikte şunlara bak" demeden önce, her fikri binlerce geçmiş örnekte ölçmek. Ezber değil, kanıtla öğretmek.

- **Veri:** 26 coinin günlük kapanışı (2019 → 2026-10).
- **Dönemler:** eğitim 2020–22, doğrulama 2023, sınav 2024 → 2026-10.
- **Sinyaller:** 25'ini baş eğitmen önerdi; 21'ini iki uzman alt ajan önerdi (teknik analist ve kantitatif araştırmacı). Uzman listesi test edilmeden önce sabitlendi (commit `a0bcd19`).
- **Kod ve tam sonuç:** `experiments/sinyal_lab/`. Ücret harcanmadı.

## Yöntem

- **Ölçüm:** Sinyal ile gelecek 5, 20 ve 60 günlük getiri arasındaki sıra korelasyonu (ρ). İki türde bakıldı:
  - zaman serisi: piyasa ya da coin yükselir mi
  - kesitsel: o gün hangi coin diğerlerini geçer
- **Örtüşme önlemi:** H günlük ufukta yalnızca H günde bir örnek alındı.
- **Hata payı:** Tarihe göre kümelendi. İlk sürümde bu yoktu; aynı gün birlikte hareket eden 26 coin bağımsız sayıldığı için t değerleri şişti ve 3 "sağlam" sinyal (BTC momentumu, BTC'ye göre göreli güç) sahte çıktı. Bu hata kantitatif araştırmacı ajanın uyarısıyla düzeltildi.
- **"Sağlam" sayılma koşulu:** eğitimde |t| ≥ 3 (138 test için sıkı eşik), ayrıca doğrulama ve sınavda aynı yön ve |t| ≥ 1,5.

## Sonuç (138 test)

**Piyasanın ya da tek coinin yönünü tahmin eden hiçbir grafik sinyali sağlam çıkmadı.** RSI, MACD, 20 günlük kırılım, Aroon, ardışık gün serisi, zaman serisi momentumu, ortalamalara uzaklık, BTC'nin gidişatı, çarpıklık ve sıkışma dahil. Bu sonuç, ajan eğitimi deneyiyle (`docs/AJAN-EGITIM-DENEYI.md`) tutarlı.

**Sağlam çıkan tek aile: "riskli/piyango coinler diğerlerinin gerisinde kalır"** (kesitsel):

| Sinyal | Ufuk | Eğitim ρ (t) | Doğrulama t | Sınav ρ (t) |
|---|---|---|---|---|
| Düşük kendine özgü (idiosenkratik) oynaklık, 60g | 5g | +0,101 (+5,2) | +2,8 | +0,104 (+4,8) |
| Düşük kendine özgü oynaklık, 60g | 20g | +0,146 (+3,8) | +3,4 | +0,156 (+3,8) |
| Düşük toplam oynaklık sırası, 30g | 5g / 20g | −0,083 / −0,129 (oynak olan geride) | −1,8 | −0,111 / −0,140 |
| MAX etkisi: son 30 günün en büyük tek gün getirisi düşük olan | 5g | +0,073 (+4,1) | +2,2 | +0,095 (+4,3) |

Sinyaller literatürde bilinen etkilerdir: Ang ve diğerleri (2006) düşük idiosenkratik oynaklık; Bali, Cakici ve Whitelaw (2011) MAX etkisi. Kantitatif araştırmacı ajan bunları önceden önermişti.

**Parasal karşılığı:** Her 20 günde yeniden seçim, %0,25 masraf, yalnızca alım.

| | Eğitim Sharpe | Doğrulama Sharpe | Sınav Sharpe |
|---|---|---|---|
| İdiosenkratik oynaklığı en düşük 1/3 | 1,18 | 1,59 | 0,36 |
| Tüm coinler eşit | 1,06 | 1,26 | 0,30 |
| En yüksek 1/3 | 0,93 | 0,34 | 0,30 |

Sıralama üç dönemde de aynı yönde, ama fark mütevazı. Bu bir zamanlama sinyali değil, **coin seçme** sinyali; düşüşler büyük kalıyor (−%58 ile −%75 arası). BTC ve ETH yapısal olarak en düşük idiosenkratik oynaklıklı coinler. Bu, geniş taramada 26 coine yayılmanın neden BTC+ETH trendinden kötü çıktığını da açıklıyor.

## Ajana öğretilecek kontrol listesi (kanıta dayalı)

1. **Piyasa yönünü grafikten tahmin etmeye çalışma.** Zamanlama için test edilmiş trend kurallarını kullan.
2. **Coin seçerken:** Son 60 günde kendine özgü oynaklığı yüksek olanlardan ve son 30 günde tek günde büyük sıçrama yapanlardan (piyango coinleri) kaçın; düşük oynaklıklı, büyük coinleri tercih et.
3. **Bir haber ya da grafik "çok güçlü" görünüyorsa bile** bu 138 testte yön bilgisi taşımadı. Kararı gerekçelendirirken bunu hatırla.

## Sınırlar ve sonraki adımlar

- **Hacim ve gün içi yüksek/düşük verisi kullanılmadı.** Uzmanların hacim tabanlı 5 önerisi (CLV, ATR kırılımı, imzalı hacim z skoru, Amihud likiditesi, VWAP sapması) Binance günlük arşivinde mevcut. Bunlar bir sonraki turda aynı ön kayıt yöntemiyle test edilebilir.
- **Evren 26 coin;** kesitsel sonuçlar daha geniş evrende tekrar sınanmalı.
- **Sonraki deney:** İdiosenkratik oynaklık filtresinin trend stratejisine eklenmesi, örneğin trendi yalnızca en düşük oynaklıklı K coinde uygulamak. Aynı eğitim, doğrulama ve sınav düzeniyle denenmeli.

## 2. tur — hacim sinyalleri ve trend filtresi (16 Kasım 2026)

### Hacim ve gün içi aralık (27 ön kayıtlı test)

Veri: Binance günlük arşivinden 26 coinin açılış, yüksek, düşük ve kapanış fiyatıyla USDT hacmi (sonuç deposunda `veri/genis/kripto_ohlcv/`). 9 sinyal veri gelmeden önce sabitlendi (`experiments/sinyal_lab/hacim_sinyalleri.py`, commit `c0462af`):
- Uzman teknik analistin 5 önerisi: CLV, ATR kırılımı, imzalı hacim z skoru, Amihud likiditesi, VWAP sapması.
- Baş eğitmenin "haber ya da ilgi kaynaklı yükseliş" fikri için 4 hacim vekili: son hafta hacmi / 3 aylık hacim, bunun coinler arası sırası, hacimle gelen 7 günlük yükseliş, piyasa hacmindeki pay değişimi.

**Sonuç: hiçbiri sağlam değil; hiçbiri eğitimde bile |t| ≥ 3'e ulaşmadı.**
- En güçlüsü ATR kırılımı, 20 gün: eğitimde t = +2,8, doğrulama ve sınavda 0.
- "Hacimle gelen yükseliş" sınavda hafif negatif (5 günde t = −2,1). Yani ilgi patlamasından sonra coin biraz geride kalma eğiliminde, ama bu sağlam değil.
- Haber ve ilgi kaynaklı hareketleri hacimden yakalayıp önden gitmek bu veride mümkün olmadı.

Tam tablo: `experiments/sinyal_lab/hacim_sonuc_2026-11-16.md`.

### Trend + idiosenkratik oynaklık filtresi

Ön kayıt: `experiments/trend_filtre/deney.py`. Kurgu: her 20 günde bir idiosenkratik oynaklığı en düşük K coin seçilir ve trend kuralları yalnızca onlara uygulanır (K ∈ {2, 3, 5, 8}). BTC, BTC'ye göre artığı sıfır olduğu için her zaman seçilir.

| | Eğitim Sharpe / düşüş | Test Sharpe / düşüş |
|---|---|---|
| BTC+ETH trend (taban) | 1,43 / −%50 | 1,01 / −%32,5 |
| K=2 (eğitimde seçilen; BTC + çoğunlukla ETH, TRX ya da BNB) | 1,48 / −%39 | 0,96 / −%19,7 |
| K=3 / 5 / 8 | 1,43 / 1,24 / 1,24 | 0,91 / 0,79 / 0,35 |

**Bağımsız denetim (alt ajan):**
- Geleceği görme hatası yok, sonuçlar tekrarlanabilir.
- Test başlangıcını bir gün kaydırmak K=2'nin test Sharpe'ını 0,96'dan 1,17'ye çıkarıyor. Yani K=2 ile taban arasındaki fark gürültü düzeyinde.
- Coin sayısı arttıkça sonuç düzenli olarak kötüleşiyor.

**Karar:** Filtre BTC+ETH trendini güvenilir biçimde geçmiyor; mevcut strateji kalır.

**Zamanlama notu (denetimden):** Testler, kararın günlük kapanış fiyatıyla uygulandığını varsayıyor. Kriptoda günlük kapanış ertesi günün açılışına eşit olduğu için bu sorun değil; canlı motor da işlemi ertesi açılışta yapıyor. ABD ETF testinde ise gece fiyat boşlukları yüzünden bu varsayım iyimser (`docs/GENIS-TARAMA.md`).

## Genel sonuç (iki tur, 165 test)

| Soru | Sonuç |
|---|---|
| Grafikten piyasanın ya da coinin yönü tahmin edilebilir mi? | Hayır: 165 testte sağlam yön sinyali yok. Ajan deneyi de aynı sonucu verdi. |
| Hacim ya da haber kaynaklı hareketler önceden yakalanabilir mi? | Hayır: 27 hacim testinden hiçbiri sağlam değil. |
| Coinler arası seçimde işe yarayan bir şey var mı? | Evet: düşük idiosenkratik oynaklık ve piyango coinlerinden kaçınma, üç dönemde de tutarlı. |
| Bu, mevcut stratejiyi iyileştiriyor mu? | Hayır: bilgi zaten BTC+ETH seçiminde var; dinamik filtre geçemedi. |

Ajanın kontrol listesi aynı kalıyor: yön tahmini yerine test edilmiş trend kuralları, seçimde düşük oynaklıklı büyük coinler, piyango coinlerinden kaçınma.
