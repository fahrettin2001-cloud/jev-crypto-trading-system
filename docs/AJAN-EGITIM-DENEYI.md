# Ajan eğitimi deneyi — grafiklerden 20 günlük yön tahmini (16 Kasım 2026)

Soru: Bir LLM ajanı, geçmiş grafiklere bakıp "20 gün sonra fiyat yüksek mi?" sorusunu tahmin ederken, uzman eleştirmen ajanların hatalarından çıkardığı derslerle eğitilerek gerçekten iyileşebilir mi?

Kod ve dersler: `experiments/ajan_egitim/`. Ücret harcanmadı: tahminci ve eleştirmen olarak bu oturumdaki ucuz alt ajanlar (Claude Haiku) kullanıldı; API kredisi, Jev ya da TradingAgents çağrısı yok.

## Tasarım

- **Bölümler:** 26 coinin günlük verisinden rastgele günler. Ajan son 90 kapanışı görür; ayrıca 30 ve 90 günlük getiri, ortalamalara uzaklık, oynaklık, zirveden uzaklık, 4 trend kuralı ve piyasa liderinin durumu verilir.
- **Gelecek bilgisi gizli:** Tarih ve coin adı yok, fiyat son kapanış = 100'e ölçekli. Bunun sebebi, dil modellerinin 2020–2024 kripto tarihini ezbere bilmesi: tarihi gösterirsek sonrasını "hatırlar". Aynı nedenle o dönemin haberleri kullanılmadı; sonradan yazılmış haberler sonucu içerir.
- **Üç ayrı dönem:**
  - eğitim: 2020-06 → 2022, 40 bölüm; eleştirmen yalnızca bunların sonucunu görür
  - doğrulama: 2023, 40 bölüm; hangi ders listesinin seçileceğine bu karar verir
  - sınav: 2024 → 2026-10, 60 bölüm; bir kez, en sonda
- **Puan:** Brier (düşük daha iyi; hep %50 demek = 0,250) ve isabet.
- **Sızıntı denetimi:** Her alt ajana izin verilen araç sayısı sınırlandı ve bitince sayıldı. Ajanlar yalnızca kendi bölüm dosyasını okudu. Sınavda dosya okuma sınırı yüzünden aynı dosyanın ikinci yarısı için bir ek okuma izni verildi.

## Sonuçlar

| Tur | Ders | Eğitim Brier | Doğrulama Brier |
|---|---|---|---|
| 1 | yok | 0,261 | **0,230** |
| 2 | 8 ders (eleştirmen 1) | 0,227 | 0,245 |
| 3 | 5 sade ders (eleştirmen 2) | 0,242 | 0,243 |
| Kıyas: hep %50 | — | 0,250 | 0,250 |
| Kıyas: taban oran | — | 0,249 | 0,246 |
| Kıyas: trend kuralı (eğitim oranlarıyla) | — | 0,230 | 0,277 |

- 2. turdaki dersler eğitimde puanı iyileştirdi ama doğrulamada kötüleştirdi: ezber (aşırı uyum).
- 3. turda eleştirmene küçük örneklere dayanan dersleri silmesi söylendi; doğrulama yine iyileşmedi.
- Doğrulamada en iyisi dersiz 1. tur. Ama onun da hep %50'ye karşı avantajı 40 örnekte istatistiksel olarak zayıf: Brier farkı %90 aralığında −0,036 ile −0,003 arası.

**Son sınav (2024 → 2026-10, 60 bölüm; daha önce hiç kullanılmadı):**

| Tahminci | Brier | İsabet |
|---|---|---|
| Dersiz (doğrulamada seçilen) | 0,243 | %58 |
| 3. tur dersleriyle (bilgi) | 0,246 | %57 |
| Taban oran (eğitimdeki yukarı oranı) | 0,245 | %62 |
| Hep %50 | 0,250 | %62 |
| Trend kuralı | 0,254 | %43 |

İki tahmincinin de taban orana göre Brier farkının %90 aralığı sıfırı içeriyor: dersiz [−0,014, +0,011], dersli [−0,010, +0,013]. **Ajan, sınavda basit taban orandan ayırt edilemedi; eleştirmen dersleri sınavda fayda sağlamadı.**

## Yorum

- 20 günlük yönü yalnızca grafikten tahmin etmek bu yöntemle mümkün olmadı. Bu sonuç bilinen gerçeklerle uyumlu: kısa vadeli kripto yönü büyük ölçüde gürültü.
- Eleştirmenle "eğitim", küçük örnekte gerçek bilgi yerine tesadüfleri derse çeviriyor. Yeni veride bu dersler fayda sağlamıyor.
- Trend stratejisinin değeri isabetli yön tahmini değil. Asıl kazancı büyük düşüşlerde nakitte durması ve yükselişlerin bir kısmını yakalaması (risk yönetimi). Bu yüzden "trend kuralı" tek tek 20 günlük tahminlerde zayıf görünse de stratejinin geçmiş testleri iyidir.

## Öneri

- LLM ajanlarına yön tahmini yaptırmak için daha fazla emek ve ücret harcamayın, ya da ancak geniş örneklemli (yüzlerce bölüm) ve tarih sızıntısı olmayan bir testle kanıt gelirse harcayın.
- Gölge moddaki ajan kurulu (TradingAgents) için de aynı ölçüt geçerli: yaklaşık 20 ölçülmüş karar biriktiğinde taban orana göre isabet raporlanmalı. Fark yoksa gece çalışması kapatılıp kredi korunabilir.
- Jev'in değeri ayrıca ölçülmeli. Bu deneyde Jev çağrısı ücretli olduğu için kullanılmadı.

## Sınırlar

- Örneklem küçük: 40 / 40 / 60 bölüm. Küçük farklar gürültü olabilir.
- Anonimleştirme tam değil. Fiyat şekli ve piyasa lideri bilgisi dönemi ima edebilir; ama bu sızıntı ajanın lehine olurdu ve yine de avantaj görülmedi.
- Tahminci ve eleştirmen ucuz bir modeldi (Haiku). Daha güçlü modeller farklı sonuç verebilir; bu test edilmedi.
