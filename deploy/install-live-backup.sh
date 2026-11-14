#!/usr/bin/env bash
# Root tarafından sunucuda çalıştırılır; canlı botun kodunu/hesabını/zamanlayıcısını değiştirmez.
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then
    echo 'Bu kurulum root ile çalıştırılmalı.' >&2
    exit 1
fi
cd /opt/jev/app
for unit in jev-backup.service jev-backup.timer; do
    if [ -e "/etc/systemd/system/$unit" ] || [ -L "/etc/systemd/system/$unit" ]; then
        echo 'Yedek birimi zaten var; mevcut ayarın üzerine yazılmadı.' >&2
        exit 1
    fi
done
test -f /var/lib/jev/canli/durum.pkl
test -f /var/lib/jev/canli/.kilit
runuser -u jev -- python3 -m venv /opt/jev/backup-venv
runuser -u jev -- /opt/jev/backup-venv/bin/python -m pip install /opt/jev/app
install -d -o jev -g jev -m 700 /var/lib/jev/backups /var/lib/jev/backup-keys
if [ ! -e /var/lib/jev/backup-keys/live.jevkey ]; then
    runuser -u jev -- /opt/jev/backup-venv/bin/python -c 'from jev.backup import create_key; create_key("/var/lib/jev/backup-keys/live.jevkey")'
fi
chown jev:jev /var/lib/jev/backup-keys/live.jevkey
chmod 600 /var/lib/jev/backup-keys/live.jevkey
cp --no-clobber deploy/jev-backup.service deploy/jev-backup.timer /etc/systemd/system/
systemctl daemon-reload
systemctl start jev-backup.service
systemctl show jev-backup.service -p Result -p ExecMainStatus --no-pager
systemctl enable --now jev-backup.timer
systemctl list-timers jev-backup.timer --no-pager
echo 'Yedekleme görevi kuruldu; ilk yedeğin ayrı klasöre geri yüklenmesi ayrıca doğrulanmalı.'
