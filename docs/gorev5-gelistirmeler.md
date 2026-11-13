# Görev 5 — Botu geliştirme: ölçüm, risk ve yeni sinyaller

Sorumlu: @demirfahrieren-png (Claude ile). Başlangıç: 13 Kasım 2026.

Jev bağlantısı @fahrettin2001-cloud'da; bu görev onunla çakışmayan, Jev geldiğinde onu daha güvenli çalıştırmaya ve ölçmeye yarayan işleri kapsar. Her alt iş ayrı PR'dır.

| # | İş | Neden | Durum |
|---|---|---|---|
| 5.1 | Oynaklığa göre pozisyon büyüklüğü | Az emekle riski azaltır | Tamamlandı (PR #21) |
| 5.2 | Karar günlüğü ve güven kalibrasyonu | "Jev %70 emin dediğinde %70 haklı mı?" sorusunu cevaplar | İncelemede (PR #22) |
| 5.3 | Canlı sanal işlem | Büyük modellerin geçmişi "bilmesi" sorununu ve gerçek koşulları ancak bu sınar; Hostinger'da saatlik çalışır | İncelemede — kurulum: `docs/CANLI-SANAL-ISLEM.md` |
| 5.4 | Haber duygu analizi | Projenin asıl fikri; Jev'e ek girdi. Haberler talimat değil veridir | Bekliyor |

## 5.3 Canlı sanal işlem

`jev/live.py` + `deploy/jev-live.service` / `jev-live.timer`. Sunucu her saat başından 1 dakika sonra `python -m jev.live run` çalıştırır: son kapanan mumlar Binance Global halka açık API'sinden (`data-api.binance.vision`) alınır, **backtest ile aynı motor** (`Simulator`) işler, sonuçlar dosyalara eklenir ve durum kaydedilir. Gerçek emir, hesap veya API anahtarı yoktur.

- Backtest motoru adım adım çalışan `Simulator` sınıfına ayrıldı; `run_backtest` onu kullanır (sonuçlar birebir aynı: 184 test, 700 rastgele senaryo ve gerçek veri sonucu değişmedi).
- Testte bot 360 saat boyunca her saat kaydedilip yeniden yüklenerek çalıştırıldı ve tek seferlik backtest ile **aynı işlemleri ve varlık eğrisini** üretti.
- Kesinti sonrası kaçırılan saatler sırayla işlenir; 2 saatten eski barlarla işlem yapılmaz (yalnızca stratejiye gösterilir). Aynı bar iki kez işlenmez; ağ hatasında durum dosyası değişmez; iki çalışma aynı anda olamaz (kilit).
- `DURDUR` dosyası: acil durdurma; bot ağa bile çıkmaz.
- Birden çok coin: `jev.strategy.Combined` her sembol için ayrı strateji çalıştırır.
- Ayrıştırıcı, 13 Kasım 2026'da alınan gerçek bir `api/v3/klines` cevabıyla da doğrulandı.

Kurulum ve günlük kullanım: [`docs/CANLI-SANAL-ISLEM.md`](CANLI-SANAL-ISLEM.md).

## 5.2 Karar günlüğü ve güven kalibrasyonu

`jev/journal.py`. Stratejinin (ileride Jev'in) her kararı — **AL, SAT ve BEKLE** — güven puanı, o andaki fiyat, kaynak (ör. `jev-1.13.0`), gerekçe ve sonucu (gerçekleşti / reddedildi: neden / bekle) ile kaydedilir. Strateji `jev.strategy.Hold` döndürerek işlem yapmadan "bekle" kararı verebilir.

**Haklı sayılma:** karar anındaki kapanıştan `horizon` bar sonraki kapanışa bakılır (varsayılan 24). Eşik varsayılan olarak bir al-sat turunun maliyetidir (2 × komisyon + 2 × kayma; %0,1 ve 5 bps ile %0,30):

- AL haklı: getiri > eşik · SAT haklı: getiri < −eşik · BEKLE haklı: |getiri| ≤ eşik

İşlemin gerçekleşip gerçekleşmediğinden bağımsızdır; risk kontrolünün reddettiği kararın da isabeti ölçülür (risk kontrolü iyi kararları mı engelliyor, görülebilir).

**Kalibrasyon:** Güven puanı olan kararlar %10'luk aralıklara bölünür; her aralıkta ortalama güven ile gerçek isabet karşılaştırılır. Fark −5 puandan kötüyse "fazla iddialı", +5'ten iyiyse "fazla çekingen", arasıysa "uyumlu". Bir aralıkta varsayılan 20'den az karar varsa "az veri" yazılır ve yorum yapılmaz. Tek sayı özeti olarak **Brier puanı** (ortalama (güven − sonuç)²; 0 mükemmel, 0,25 yazı-tura düzeyi) verilir; Jev sürümlerini karşılaştırmak için kullanılabilir.

```bash
# Backtest + isabet raporu; --out ile kararlar.csv, --journal ile JSONL günlüğe ekleme
python -m jev.backtest --prices ... --fast 24 --slow 96 --calibration --journal kararlar.jsonl --out sonuc/
# Kayıtlı bir günlüğü (ör. canlı sanal işlemden) sonradan değerlendirme
python -m jev.journal --journal kararlar.jsonl --prices ... --kline-symbols BTCUSDT --horizon 24
```

Jev için: Jev'in cevabındaki güven (`confidence`) `OrderIntent(..., confidence=...)` ya da `Hold(..., confidence=...)` içine yazılırsa rapor doğrudan çalışır. Kaynak alanına model sürümü (`jev-1.13.0`) yazılması önerilir; TypeSafe takma adların (`jev-latest`) zamanla değişebileceğini belirtiyor.

**Gerçek veride (BTCUSDT 1s, Ağu–Eki 2026, SMA 24/96, 24 saat ufuk, %0,30 eşik):** 22 karar, genel isabet %31,8 (AL %36,4, SAT %27,3). SMA güven puanı vermediği için kalibrasyon tablosu yok. Kesişim sinyalleri 24 saatlik yönü tahmin etmekte yazı-turadan iyi değil; strateji kârını yönü tutturmaktan değil, yükselişte uzun süre pozisyonda kalmaktan elde etti. Bu, "isabet oranı" ile "kârlılığın" farklı şeyler olduğunu gösteriyor.

**Sınırlar:** Yalnızca kapanış fiyatına bakılır (ufuk içindeki yol önemsenmez). Tek bir ufuk seçilir; Jev'in kararlarının hangi süreye göre verildiği netleşince ufuk ona göre ayarlanmalı. Kalibrasyon için yüzlerce karar gerekir; birkaç haftalık canlı sanal işlem (5.3) bunun için gerekli.

## 5.1 Oynaklığa göre pozisyon büyüklüğü

`jev/sizing.py` → `VolatilityTargetSizer`. Piyasa sakinken büyük, çalkantılıyken küçük pozisyon:

```
oran = hedef_günlük_oynaklık / gerçekleşen_günlük_oynaklık   (0 ile max_fraction arasına kırpılır)
gerçekleşen = son `window` barın log getirilerinin std'si × √(günlük bar sayısı)
alış tutarı = min(toplam varlık × oran, nakit)
```

Geçmiş yetersizse oran bilinmez ve alış yapılmaz. `SmaCross(..., sizer=...)` ile ya da komut satırında:

```bash
python -m jev.backtest --prices ... --fast 24 --slow 96 --vol-target 0.01 --vol-window 72 --bars-per-day 24
```

`--fraction` bu durumda üst sınır (`max_fraction`) olarak kullanılır. Risk limitleri ayrıca ve her durumda uygulanır.

### Gerçek veride sonuç (BTCUSDT 1s, Ağu–Eki 2026, SMA 24/96, gerçek kurallar, kayma 5 bps)

Bu dönemde BTC'nin 72 saatlik günlük oynaklığı %0,70 – %4,27 arasında, medyanı %1,62 idi. Bu yüzden %2 ve üstü hedefler çoğu zaman %95 üst sınırına takılıp sabit oranla aynı sonucu verdi.

| Hedef günlük oynaklık | Getiri | En büyük düşüş |
|---|---|---|
| Yok (sabit %95) | +8,83% | %13,79 |
| %1,75 | +9,06% | %13,77 |
| %1,5 | +9,42% | %13,50 |
| %1,25 | +9,86% | %12,58 |
| %1 | +11,88% | %10,96 |
| %0,75 | +14,11% | %9,16 |
| %0,5 | +11,50% | %6,63 |

Sentetik veride (farklı rejimler): sabit +29,00% / düşüş %30,36; hedef %2 → +21,69% / %15,05; hedef %1 → +11,03% / %7,86.

**Yorum:** Hedef düştükçe en büyük düşüş her iki veri setinde de düzenli olarak azaldı — beklenen ve güvenilir etki bu. Getiri ise hedefe göre düzenli değişmedi (gerçek veride inip çıktı, sentetikte azaldı). Tek dönemde en iyi görünen hedefi seçmek ezber (overfitting) olur; hedef, kabul edilebilir düşüşe göre seçilmeli. Ekipçe seçilen "temkinli" risk paketiyle birlikte günlük %1 civarı makul bir başlangıç önerisidir.

### Sınırlar

- Oynaklık geçmişe bakar; ani şoklarda gecikmeli tepki verir.
- Yalnızca giriş büyüklüğünü ayarlar; açık pozisyonu oynaklık arttıkça küçültmez (yeniden dengeleme yok).
- Tek sembol için hesaplanır; semboller arası bağıntı hesaba katılmaz.
