# Canlı sanal işlem — Hostinger kurulumu

Durum: Görev 5.3, inceleme bekliyor. **Gerçek emir göndermez, hesap veya API anahtarı kullanmaz.** Yalnızca Binance Global'in halka açık mum verisini (`data-api.binance.vision`) okur ve sahte parayla işlem yapar.

## Nasıl çalışır?

Sunucu her saat başından 1 dakika sonra `python -m jev.live run` komutunu bir kez çalıştırır. Komut son kapanan saatlik mumu alır, **backtest ile aynı motorla** (aynı strateji, komisyon, kayma, Binance kuralları, risk limitleri) karar verir, sonucu dosyalara ekler ve kapanır. Kesinti olursa sonraki çalışma kaçırılan saatleri sırayla işler; 2 saatten eski barlarla işlem yapılmaz, yalnızca stratejiye gösterilir.

Testte bot 360 saat boyunca her saat kaydedilip yeniden yüklenerek çalıştırıldı ve aynı fiyatlarla tek seferde yapılan backtest ile **birebir aynı** işlemleri ve varlık eğrisini üretti (`tests/test_live.py`).

Durum klasöründeki dosyalar (`/var/lib/jev/canli`):

| Dosya | İçerik |
|---|---|
| `islemler.csv` | Her sanal işlem: zaman, sembol, yön, tür, miktar, fiyat, komisyon, K/Z, gerekçe |
| `kararlar.jsonl` | Her karar (AL/SAT/BEKLE), güven ve sonucu — karar isabeti raporu için |
| `varlik_egrisi.csv` | Her saat toplam varlık |
| `redler.csv` | Reddedilen öneriler ve nedenleri |
| `gunluk.log` | Her çalışmanın özeti ve uyarılar |
| `ayarlar.json` | Başlatma ayarları |
| `durum.pkl` | Botun kaldığı yer (yalnızca bu programın yazdığı dosya; elle değiştirmeyin) |
| `DURDUR` | Varsa bot hiçbir şey yapmaz (acil durdurma) |

## Kurulum (bir kez, ~10 dakika)

Hostinger panelinden VPS'in IP adresini alın. **Sunucu şifresini veya SSH anahtarını GitHub'a, ortak notlara ya da yapay zekâ sohbetlerine yazmayın.** Komutlar Ubuntu 22.04 / 24.04 içindir.

```bash
# 1. Sunucuya bağlan (kendi bilgisayarının terminalinden)
ssh root@SUNUCU_IP

# 2. Gerekenler (Python 3.10+ ve git)
apt update && apt install -y python3 git
python3 --version

# 3. Bot için ayrı, yetkisiz bir kullanıcı ve klasörler
adduser --system --group --home /opt/jev jev
mkdir -p /var/lib/jev && chown jev:jev /var/lib/jev

# 4. Kodu indir (depo herkese açık)
git clone https://github.com/fahrettin2001-cloud/jev-crypto-trading-system /opt/jev/app
chown -R jev:jev /opt/jev/app
cd /opt/jev/app

# 5. Sunucu Binance verisine ulaşabiliyor mu?
sudo -u jev python3 -m jev.live check
#   "Bağlantı tamam ..." görmelisiniz. Hata alırsanız dur ve ekibe yaz.

# 6. Sanal hesabı başlat (ekip kararı: BTCUSDT + ETHUSDT, "temkinli" risk paketi)
#    500 USDT bütçeyle: işlem başına %10 = 50, tek coinde %30 = 150,
#    nakitte en az %40 = 200. Bütçe farklı seçilirse tutarları ona göre değiştirin.
#    --max-trade-notional hem risk sınırı hem de stratejinin alış tutarı üst sınırıdır.
sudo -u jev python3 -m jev.live init --dir /var/lib/jev/canli \
    --symbols BTCUSDT ETHUSDT --cash 500 \
    --max-trade-notional 50 --max-position-notional 150 --min-cash-reserve 200

# 7. Saatlik çalışmayı aç
cp deploy/jev-live.service deploy/jev-live.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now jev-live.timer

# 8. Kontrol
systemctl list-timers jev-live.timer          # bir sonraki çalışma zamanı
systemctl start jev-live.service              # hemen bir kez çalıştır (isteğe bağlı)
journalctl -u jev-live -n 20 --no-pager       # son çalışmaların çıktısı
```

Varsayılan strateji: her coin için SMA 24/96 kesişimi, oynaklığa göre pozisyon (günlük %1 hedef; alış tutarı `--max-trade-notional` ile sınırlı), komisyon %0,1, kayma 5 bps, Binance Global işlem kuralları, bar hacminin en fazla %1'i. Başka ayarlar: `python3 -m jev.live init -h`. Günlük zarar sınırı PR #11 birleşince eklenecek.

## Günlük kullanım

```bash
cd /opt/jev/app
sudo -u jev python3 -m jev.live status --dir /var/lib/jev/canli   # performans + karar isabeti
tail -n 20 /var/lib/jev/canli/gunluk.log
```

**Acil durdurma** (bot hiçbir şey yapmaz, ağa bile çıkmaz):

```bash
sudo -u jev touch /var/lib/jev/canli/DURDUR      # durdur
sudo -u jev rm /var/lib/jev/canli/DURDUR         # devam et (eski barlarla işlem yapmaz)
systemctl disable --now jev-live.timer           # zamanlayıcıyı tamamen kapat
```

**Sonuçları paylaşmak:** kendi bilgisayarınızdan `scp -r root@SUNUCU_IP:/var/lib/jev/canli ./canli-sonuc` ile indirip ekiple paylaşın (içinde gizli bilgi yoktur).

**Kodu güncellemek:** `cd /opt/jev/app && sudo -u jev git pull`. Strateji veya motor kodu değiştiyse eski `durum.pkl` yüklenemeyebilir; o durumda eski klasörü saklayıp yeni bir klasörle (`--dir /var/lib/jev/canli-2`) yeniden `init` edin ve `deploy/jev-live.service` içindeki yolu güncelleyin.

Gerçek BTCUSDT verisinde (Ağu–Eki 2026) bu ayarlarla: 22 işlem, red yok, +1,12% getiri, en büyük düşüş %1,53, komisyon 1,10 USDT. İşlemler küçük (≈50 USDT) olduğu için getiri ve düşüş de küçüktür.

## Sonuçları GitHub'a otomatik yayınlama (isteğe bağlı)

Sunucu her gün 05:20 UTC'de (08:20 TR) `son/` klasörünü (durum raporu, işlemler, kararlar, varlık eğrisi, son günlük satırları, sunucu bilgisi) **ayrı bir sonuç deposuna** yükler. Böylece sunucuya girmeden takip edilebilir; Claude'un günlük özet görevi de buradan okur.

Güvenlik: Sunucu yalnızca bu sonuç deposuna yazabilen bir **deploy key** kullanır; ana kod deposuna yazma yetkisi yoktur. Anahtar sunucuda `jev` kullanıcısına aittir ve dışarı çıkmaz. GitHub'ın sunucu anahtarı betikte sabitlidir (parmak izi `SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU`, GitHub dokümanıyla aynı). Sonuçlarda şifre veya anahtar yoktur; depo herkese açıksa sanal işlem sonuçları da herkese açık olur.

1. GitHub'da boş bir depo oluşturun, ör. `jev-canli-sonuclar` (README eklemeden).
2. Sunucuda (root): `bash /opt/jev/app/deploy/sonuc-anahtar.sh anahtar` — çıkan `ssh-ed25519 ...` satırını kopyalayın.
3. GitHub'da sonuç deposu → **Settings → Deploy keys → Add deploy key**: satırı yapıştırın, **Allow write access** işaretleyin.
4. Sunucuda (root): `bash /opt/jev/app/deploy/sonuc-anahtar.sh bagla git@github.com:KULLANICI/jev-canli-sonuclar.git` — ilk yayını yapar.
5. Günlük yayını açın:

```bash
cp /opt/jev/app/deploy/jev-sonuc.service /opt/jev/app/deploy/jev-sonuc.timer /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now jev-sonuc.timer
systemctl list-timers jev-sonuc.timer --no-pager
```

Elle yayın: `systemctl start jev-sonuc.service`. Erişimi kaldırmak: GitHub'da deploy key'i silin ve `systemctl disable --now jev-sonuc.timer`.

## Sınırlar ve riskler

- Sunucunun Binance'e erişimi bölgeye göre değişebilir; 5. adımdaki `check` bunu doğrular.
- Sunucu saati doğru olmalı (Ubuntu'da varsayılan olarak `systemd-timesyncd` açıktır).
- Durum dosyası `pickle` biçimindedir; yalnızca botun kendi yazdığı dosya yüklenmelidir.
- Sanal sonuçlar gerçek emirlerdeki kısmi gerçekleşme, gecikme ve sipariş defteri derinliğini tam yansıtmaz.
- Kalibrasyon tablosu için yüzlerce karar gerekir; SMA günde birkaç karar verir. Jev bağlanınca (karar sayısı artınca) rapor anlamlı hale gelir.

## Jev gölge modu (isteğe bağlı)

Bota Jev eklemek için önce yalnızca gölge mod kullanılır: Jev'e düzenli soru sorulur, cevap kaydedilir, işlemler değişmez. Kurulum ve sorulan sorunun anlamı: [JEV-GOLGE-CANLI.md](JEV-GOLGE-CANLI.md).
