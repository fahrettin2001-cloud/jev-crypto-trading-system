# Canlı sanal botun düzenli şifreli yedeği

SQLite yedeğinden ayrıdır. Hostinger'daki bot `durum.pkl`, `ayarlar.json`, CSV ve
karar günlüğü dosyalarıyla çalışır. Bu araç sadece bu durum klasörünü yedekler;
Hermes konteyneri, /etc içindeki servis anahtarları ve bütün VPS yedeği değildir.

## Davranış

- `jev.live` ile aynı `.kilit` flock dosyası kullanılır. Yazma sırasında yedek
  alınmaz; systemd beş dakika sonra yeniden dener. Başka bot çalışması durdurulmaz.
- Dosyalar bellekte toplanır; her dosya SHA-256 ve bütün arşiv AES-256-GCM ile
  korunur. Şifresiz geçici kopya üretilmez. Kaynak dosyalar ve eski yedekler silinmez.
- Ayar ve durum zorunlu; CSV/günlük, karar ve gölge günlükleri varsa dahil edilir.
  DURDUR dosyası varsa korunur. Beklenmeyen dosya, sembolik bağ, fazla boyut veya
  eksik durum hatadır. `.kilit` ve yarım `durum.pkl.tmp` yedeğe alınmaz.
- Geri yükleme sadece yeni 0700 klasöre, 0600 dosyalarla yapılır. Yol geçişi ve
  mevcut dosya üzerine yazma reddedilir. Pickle restore sırasında çalıştırılmaz.
  Botu başlatırken yalnızca güvenilir anahtarınızla oluşturulmuş kendi yedeğinizi kullanın.
- Linux/POSIX sunucu hedeflenir. Bellek/swap güvenliği sistemin sorumluluğundadır.

## Sunucuda kurulum

Kod güncel ana dalda ve `python3-venv` kurulu olmalıdır. İlk kurulum root ile:

```bash
bash /opt/jev/app/deploy/install-live-backup.sh
```

Bu betik `/opt/jev/backup-venv` ortamını ve sadece bu işe ait yeni service/timer'ı
kurar. Mevcut yedek birimleri varsa üzerine yazmaz. İlk yedek başarılı olmadan
günlük zamanlama açılmaz. Canlı işlem servisi ve zamanlayıcısı değiştirilmez.

Kaynak `/var/lib/jev/canli`, çıktı `/var/lib/jev/backups`, anahtar
`/var/lib/jev/backup-keys/live.jevkey`. Yalnızca jev kullanıcısına açık yerel
anahtar kullanılır; içeriği ekrana yazılmaz. Anahtar kaybolursa yedekler açılamaz.
Anahtarın ayrıca güvenli bir sır deposunda korunması ekip sorumluluğundadır.

Günlük saat 00:20 UTC = **03.20 Türkiye**; bilgisayar kapalıyken kaçırılan görev
sonraki açılışta çalışır. Eski yedekler otomatik silinmez; disk kullanımı izlenmeli.

## Doğrulama ve kurtarma

```bash
systemctl show jev-backup.service -p Result -p ExecMainStatus --no-pager
systemctl list-timers jev-backup.timer --no-pager
journalctl -u jev-backup.service -n 10 --no-pager
ls -lh /var/lib/jev/backups
```

Bir yedeği ayrı, henüz var olmayan klasöre geri yükleyin:

```bash
sudo -u jev /opt/jev/backup-venv/bin/python -m jev.live_backup restore \
  --source /var/lib/jev/backups/YEDEK_DOSYASI.jevbackup \
  --destination /var/lib/jev/kurtarma-denemesi \
  --key-file /var/lib/jev/backup-keys/live.jevkey
cd /opt/jev/app
sudo -u jev /opt/jev/backup-venv/bin/python -m jev.live status --dir /var/lib/jev/kurtarma-denemesi
```

Dosyadaki varlık, pozisyonlar, ayarlar ve son işlenen mum kontrol edilir. Doğrulama
sırasında geri yüklenen botun `run` komutu çalıştırılmaz; ikinci canlı süreç başlatılmaz.
Asıl hesaba dönme işlemi bot durdurularak ayrı kurtarma planıyla yapılır.

**Aynı sunucudaki yedek, sunucunun tamamen kaybına karşı yeterli değildir.**
İkinci depolama ve anahtarın ayrı muhafazası henüz bu kurulumun parçası değildir.
Dış depolama seçildiğinde şifreli arşivlerin aktarılması ayrıca kurulmalıdır.

## Doğrulama durumu

Sekiz otomatik test: birebir dosya dönüşü, DURDUR korunması, kilit çakışması,
yanlış anahtar/bozulma, mevcut dosya koruması, sembolik bağ, bilinmeyen/eksik dosya,
yol geçişi, yazım hatası temizliği ve gerçek sentetik bot durumunun aynı sonuçla
sürmesi. Sunucuda kurulum ve saatli çalışma, kullanıcı konsol çıktısıyla ayrıca
kanıtlanmalıdır; betiğin repoda bulunması kurulduğu anlamına gelmez.
