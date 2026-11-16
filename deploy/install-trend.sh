#!/usr/bin/env bash
# Root ile calistirilir. Trend toplulugunu IKINCI sanal hesap olarak baslatir.
# Mevcut canli sanal botu (/var/lib/jev/canli, jev-live.timer) DEGISTIRMEZ.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo 'Root ile calistirin.' >&2; exit 1; }
cd /opt/jev/app
DIR=/var/lib/jev/trend
if [ -e "$DIR/durum.pkl" ]; then
    echo "$DIR zaten baslatilmis; hesap yeniden kurulmadi."
else
    install -d -o jev -g jev -m 750 "$DIR"
    # Ekip karari: 500 USDT, BTCUSDT+ETHUSDT, "temkinli" limitler (50 / 150 / 200).
    # --fraction 0.6: trend tam acikken varligin %60'i yatirimda (coin basina %30 = 150 USDT sinirina denk).
    runuser -u jev -- python3 -m jev.live init --dir "$DIR" \
        --strategy trend --interval 1d --fraction 0.6 \
        --symbols BTCUSDT ETHUSDT --cash 500 \
        --max-trade-notional 50 --max-position-notional 150 --min-cash-reserve 200
fi
cp deploy/jev-trend.service deploy/jev-trend.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now jev-trend.timer
systemctl list-timers jev-trend.timer --no-pager
echo 'Trend sanal hesabi kuruldu. Ilk alim/satim kararlari bir sonraki gunluk kapanista (03:05 TR) verilir.'
echo 'Sonuclar jev-sonuc ile son/trend/ altina yayinlanir.'
