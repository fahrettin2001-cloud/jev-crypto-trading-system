#!/usr/bin/env bash
# Root ile calistirilir. Bedava duygu endeksini kurar: gecmis veriyi indirir, gecmis
# testini calistirir, gunluk kaydi acar. Canli botu ve ajanlari DEGISTIRMEZ.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo 'Root ile calistirin.' >&2; exit 1; }
cd /opt/jev/app
install -d -o jev -g jev -m 750 /var/lib/jev/duygu
echo '== Gecmis veri indiriliyor (1-2 dk) =='
runuser -u jev -- python3 -m jev.duygu indir --dir /var/lib/jev/duygu
echo '== Gecmis testi =='
runuser -u jev -- python3 -m jev.duygu test --dir /var/lib/jev/duygu --out /var/lib/jev/duygu/gecmis_testi.md
cp deploy/jev-duygu.service deploy/jev-duygu.timer /etc/systemd/system/
systemctl daemon-reload
systemctl start jev-duygu.service
systemctl enable --now jev-duygu.timer
cat /var/lib/jev/duygu/duygu_ozet.md
systemctl list-timers jev-duygu.timer --no-pager
echo 'Duygu endeksi kuruldu. Sonuclar jev-sonuc ile son/duygu/ altina yayinlanir.'
