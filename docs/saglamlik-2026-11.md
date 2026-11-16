# Sağlamlık testi sonucu — 13 Kasım 2026

Araç: `python -m jev.saglamlik --veri <klasör>` (`jev/saglamlik.py`). Veri: Binance Global 1 saatlik mumlar, BTCUSDT ve ETHUSDT, Kasım 2024 – Ekim 2026 (her iki sembolde 17.520 mum). Veri Hostinger sunucusunda `jev.binance_data` ile indirildi; her dosya Binance'in yayımladığı SHA-256 değeriyle doğrulandı. Dosyalar [`jev-canli-sonuclar/veri`](https://github.com/demirfahrieren-png/jev-canli-sonuclar/tree/main/veri) klasöründe. Eylül 2026 BTC dosyası, daha önce bağımsız indirilen kopyayla birebir aynı.

## Yorum

- **Masraflar düşülünce hiçbir ayar kâr etmiyor.** 15 ayarın 15'i de iki yılda zararda. Canlı bottaki 24/96 ayarı 2. sırada ama sonucu yine –%9,9. Aynı dönemde eşit ağırlıklı al-tut yaklaşık %0 getirdi (BTC +%10,6, ETH –%10,7).
- **Sinyal tek başına bir şey yakalıyor, ama masraflar onu yiyor.** Komisyon ve kayma olmasa 24/96 +%18,4 getiriyor. Gerçekçi masraflarla –%9,9'a düşüyor. İki yılda 482 işlem yapılıyor ve ödenen komisyon başlangıç sermayesinin %18,7'si. Kayma 10 bps olursa sonuç –%17,8, 20 bps olursa –%31,5.
- **Düşüş daha küçük ama bedava değil.** En büyük düşüş –%32,9; al-tutta bu –%60,7. Ancak strateji ortalama yalnızca %39 yatırımda kalıyor. Al-tutu aynı orana ölçeklersek düşüş –%23,9 oluyor, yani daha da küçük.
- **Geçmişin en iyisini seçmek geleceğe taşınmıyor.** Her çeyrekte bir önceki çeyreğin en iyi ayarını seçmek, ilk çeyrek hariç –%15,9 getiriyor. Bu, ızgara ortancasından (–%26,1) iyi ama yine zarar. 24/96, 9 çeyreğin 4'ünde kârda.
- **Canlı ayar** (500 USDT, temkinli limitler): sermayenin ortalama %10'u yatırımda, iki yılda –%4,9 getiri, en büyük düşüş –%12,2. Sanal bot bu stratejiyle **yavaş yavaş zarar etmeye** ayarlı. Altyapı denemesi olarak çalışmaya devam edebilir, ama sonucunu kâr beklentisiyle izlemeyin.

**Sonuç:** Bu strateji, şimdiki hâliyle gerçek paraya uygun değil. "Gerçek paraya geçiş" ölçütlerinin ilki (sağlamlık testi) geçilemedi.

## Ne denenebilir (her biri bu araçla test edilmeli)

1. **Daha az işlem:** 4 saatlik ya da günlük mum; kesişime bir eşik bandı ekleme (ör. ortalamalar %0,5 ayrışmadan işlem yapmama); en kısa tutma süresi.
2. **Daha ucuz işlem:** Limit (maker) emirlerle girip çıkma, BNB ile komisyon indirimi.
3. **Başka sinyaller:** Jev gölge modu ve 5.4 haber duygu analizi ölçüldükten sonra filtre olarak eklenebilir.

Çok sayıda fikir denemek de geçmişe uydurma riskidir. Her yeni fikrin 2. ve 3. bölümlerdeki komşuluk ve ileriye dönük seçim testlerini geçmesi gerekir; yalnızca en iyi tek sonucu göstermesi yetmez.

## Ham rapor

### Strateji sağlamlık testi — BTCUSDT, ETHUSDT

Veri: Binance 1 saatlik mumlar, 2024-11-01 → 2026-11-01 (17520 bar). Komisyon %0,1, kayma 5 bps, sonraki bar açılışında işlem.
Geçmiş sonuç gelecekteki getiriyi göstermez.

#### 1. Özet

| | Toplam getiri | En büyük düşüş | İşlem | Komisyon | Ort. yatırım oranı |
|---|---|---|---|---|---|
| Sinyal 24/96 (limitsiz, oynaklık hedefli) | -9.9% | -32.9% | 482 | %18.66 | %39 |
| Canlı ayar (500 USDT, 50/150/200) | -4.9% | -12.2% | 482 | %4.79 | %10 |
| Eşit ağırlıklı al-tut (masrafsız) | -0.0% | -60.7% | — | — | %100 |
| Al-tut × sinyalin yatırım oranı | -0.0% | -23.9% | — | — | %39 |

#### 2. Ayar ızgarası (sinyal modu, toplam getiri)

Satır: hızlı ortalama (saat), sütun: yavaş ortalama (saat). Kalın: canlı ayar.

| hızlı \ yavaş | 48 | 96 | 168 | 240 |
|---|---|---|---|---|
| 6 | -41.1% | -32.2% | -42.0% | -29.0% |
| 12 | -16.0% | -22.0% | -31.1% | -13.3% |
| 24 | -29.3% | **-9.9%** | -27.9% | -20.1% |
| 48 |  | -13.5% | -9.3% | -14.4% |

- 24/96, 15 ayar içinde **2.** sırada. Ortanca ayar -22.0%, en iyi -9.3%, en kötü -42.0%.
- Ayarların 0/15 tanesi kârda. 0/15 tanesi aynı yatırım oranlı al-tutu geçiyor.
- Oynaklık hedefi olmadan (sabit pay): ortanca -30.0%, kârda olan 0/15.

#### 3. Çeyrek çeyrek

| Çeyrek | Al-tut | Sinyal 24/96 | Canlı ayar | O çeyreğin en iyisi (sonradan) | İleriye dönük seçim (geçen çeyreğin en iyisi) |
|---|---|---|---|---|---|
| 2024-Ç4 | +32.8% | +11.0% | +3.57% | 12/48: +16.3% | — (ilk çeyrek) |
| 2025-Ç1 | -28.5% | -19.7% | -8.12% | 12/48: -14.1% | 12/48: -14.1% |
| 2025-Ç2 | +32.5% | +9.0% | +2.63% | 24/48: +11.5% | 12/48: +10.6% |
| 2025-Ç3 | +29.9% | +17.3% | +4.25% | 48/96: +21.8% | 24/48: +2.4% |
| 2025-Ç4 | -25.6% | -5.8% | -1.26% | 24/96: -5.8% | 48/96: -6.0% |
| 2026-Ç1 | -25.8% | -6.7% | -3.07% | 12/96: -0.8% | 24/96: -6.7% |
| 2026-Ç2 | -19.2% | -10.0% | -2.80% | 48/240: +2.7% | 12/96: -11.2% |
| 2026-Ç3 | +55.0% | +10.2% | +2.59% | 48/168: +20.9% | 48/240: +20.5% |
| 2026-Ç4 | -11.4% | -9.4% | -2.17% | 6/240: -4.0% | 48/168: -7.9% |

- 24/96 4/9 çeyrekte kârda.
- İlk çeyrek hariç birleşik getiri: ileriye dönük seçim -15.9%, sabit 24/96 -18.8%, ızgara ortancası -26.1%.
  İleriye dönük seçim ortancadan belirgin iyi değilse, ızgaradaki en iyi ayarı seçmek geleceğe taşınmıyor demektir.

#### 4. Maliyet duyarlılığı (sinyal 24/96)

| Varsayım | Toplam getiri | İşlem | Komisyon |
|---|---|---|---|
| masrafsız (yalnızca sinyalin kendisi) | +18.4% | 482 | %0.00 |
| komisyon %0,075 (BNB) | -5.8% | 482 | %14.31 |
| komisyon %0,1 (varsayılan) | -9.9% | 482 | %18.66 |
| kayma 10 bps | -17.8% | 482 | %17.84 |
| kayma 20 bps | -31.5% | 482 | %16.35 |

Notlar: Al-tut masrafsızdır. Strateji ilk günlerde ısınma için bekler. Izgarada en iyi sonucu seçmek iyimser bir yanılgıdır; asıl ölçü 2 ve 3. bölümlerdir.
