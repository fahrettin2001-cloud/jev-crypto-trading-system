# Jev gölge modu (canlı sanal bot yanında, kararları değiştirmeden)

Hostinger'daki canlı sanal botun yanında Jev'e (TypeSafe System One) düzenli olarak
**aynı soruyu** sorar ve cevabı kaydeder. Bot, Jev'in cevabına göre **hiçbir şey
yapmaz**. Amaç birkaç hafta veri toplayıp Jev'in olasılıklarının tutarlı olup olmadığını
ölçmek. Kod: `jev/jev_golge.py`, `jev/live.py` (`golge`, `golge-dene` komutları).

## Sorulan soru ve kaydedilen olasılığın anlamı

> **Tahmin anındaki kapanıştan `ufuk_bar` mum sonraki kapanış daha YÜKSEK mi?**

| Alan | Anlamı |
|---|---|
| `tahmin_zamani` | En son kapanan mumun kapanış zamanı (UTC). Jev yalnızca bu ana kadarki kapanışları görür. |
| `fiyat` | O mumun kapanış fiyatı (USDT). |
| `hedef_zaman` | `tahmin_zamani + ufuk_bar × mum süresi`. 1 saatlik mum ve varsayılan `ufuk_bar: 24` için **24 saat sonra**. |
| `olasilik` | Jev'in "evet, daha yüksek olacak" ihtimali, 0–1 arası. `0.70` = %70. |
| `yukseldi` (rapor) | `hedef_zaman` kapanışı `fiyat`tan **kesinlikle** büyükse 1, eşit ya da düşükse 0, henüz gelmediyse `bekliyor`. |

Komisyon veya kâr eşiği yoktur. Bu bir kâr ölçüsü değil, olasılıkların ne kadar doğru
ayarlandığının ölçüsüdür. Anlam, çevrimdışı `jev.shadow` (PR #27) ile aynıdır.

Jev'e giden veri yalnızca halka açık Binance kapanışlarıdır (varsayılan son 72 mum). Hesap,
bakiye, pozisyon, işlem ya da kişisel bilgi gönderilmez. Soru metni: `jev_golge.question_text`.

## Yalıtım: işlemler neden etkilenmez?

- Saatlik çalışmada önce işlemler yapılır ve durum diske kaydedilir. Gölge mod **ondan sonra** çalışır.
- Strateji, risk ve simülatör Jev'i hiç görmez. Jev'in cevabı yalnızca `golge.jsonl` dosyasına yazılır.
- Jev hata verir, takılır (varsayılan 30 sn zaman aşımı) ya da saçma bir cevap dönerse günlüğe tek satır yazılır, bot normal devam eder. Hata metinleri günlüğe kopyalanmaz.
- `tests/test_jev_golge.py`, gölge mod kapalı, açık, Jev çöküyor, Jev yavaş ve Jev bozuk cevap durumlarının **birebir aynı** işlemleri ve dosyaları ürettiğini doğrular. Testler anahtarsız ve ağsız çalışır (sahte Binance, sahte Jev).

## Ayarlar (`/var/lib/jev/canli/jev_golge.json`)

Dosya yoksa gölge mod kapalıdır.

```json
{"etkin": true, "ufuk_bar": 24, "her_n_bar": 4, "gunluk_cagri_siniri": 24,
 "zaman_asimi_sn": 30, "gecmis_bar": 72, "model": "jev-latest"}
```

- `her_n_bar: 4` ile 1 saatlik mumda 00, 04, 08 … UTC'de her sembol için bir soru sorulur. BTC + ETH için günde 12 çağrı yapılır.
- `gunluk_cagri_siniri`, UTC günü başına toplam çağrı tavanıdır (ücret koruması).
- Eski veriyle soru sorulmaz. Aynı mum için iki kez sorulmaz. Kesinti sonrası geriye dönük toplu soru da sorulmaz.
- **Ücret:** Her çağrı TypeSafe kredisi harcar. Güncel fiyat için TypeSafe'in ücret sayfasına bakın. SDK'nın kendi otomatik yeniden denemeleri varsa çağrı sayısı artabilir; ilk hafta TypeSafe panelinden harcamayı kontrol edin.

## Kurulum (Hostinger, anahtar sahibi yapar)

API anahtarı **asla** GitHub'a, sohbete, ekran görüntüsüne veya ortak notlara yazılmaz. Anahtarı sunucuda yalnızca sahibi (@fahrettin2001-cloud) girer.

```bash
sudo -u jev git -C /opt/jev/app pull -q
apt-get install -y python3-venv          # yoksa
bash /opt/jev/app/deploy/jev-golge-kur.sh kur    # anahtarı ekranda göstermeden sorar
bash /opt/jev/app/deploy/jev-golge-kur.sh dene   # 1 ücretli deneme çağrısı
```

`kur` şunları yapar:

- `/opt/jev/venv` içine `typesafe-sdk==0.7.5` kurar.
- Anahtarı `/etc/jev/typesafe.env` dosyasına yazar (root, 600).
- `jev_golge.json` dosyasını varsayılanlarla oluşturur.
- `deploy/jev-golge.conf` ekini `/etc/systemd/system/jev-live.service.d/` altına koyar. Bu ek, `jev-live` servisini venv Python'u ve anahtar ortam değişkeniyle çalıştırır. İşlem kodu ve ayarları değişmez.

Kapatmak:

- `jev-golge-kur.sh kapat` gölge modu kapatır (`etkin: false`).
- `jev-golge-kur.sh kaldir` eki ve anahtar dosyasını siler; bot eski hâline döner.

## Sonuçları okumak

`python3 -m jev.live golge --dir /var/lib/jev/canli` şunları gösterir:

- Kayıtlı, sonuçlanan ve bekleyen tahmin sayısı.
- **Brier puanı** (0 mükemmel, düşük iyi) ve iki karşılaştırma: hep %50 diyen (0,25) ve dönemin yükseliş oranını bilen tahminci.
- %50 dışındaki tahminlerde yön isabeti.
- Olasılık aralıklarına göre gerçekleşen oran ("%70 dediğinde %70 tutuyor mu?").

30–50 sonuçtan azında yorum yapılmaz. Günlük sonuç yayını `son/golge.txt`, `son/golge.jsonl` ve `son/golge_sonuclar.csv` dosyalarını da `jev-canli-sonuclar` deposuna koyar.

Jev çıktılarının herkese açık depoda yayınlanması TypeSafe kullanım koşullarına aykırıysa bu dosyalar `deploy/sonuc-yayinla.sh` listesinden çıkarılmalı.

## Sonraki adım (bu PR'ın dışında)

Jev ancak yeterli veriyle iki karşılaştırmayı da anlamlı farkla geçerse, stratejiye filtre ya da onay olarak eklenmesi ayrı bir PR'da önerilir. Risk limitleri her durumda geçerli kalır.
