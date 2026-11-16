#!/usr/bin/env bash
# Root ile sunucuda calistirilir. Canli sanal botun kodunu, hesabini ve zamanlayicisini
# DEGISTIRMEZ. TradingAgents'i ayri bir sanal ortama kurar ve gunluk golge analizi acar.
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then
    echo 'Bu kurulum root ile calistirilmali.' >&2
    exit 1
fi
# Sabitlenmis surum: v0.7.1 (2026-11-04). Guncellemeden once ekipce inceleyin.
TA_REPO=${TA_REPO:-https://github.com/TauricResearch/TradingAgents}
TA_REF=${TA_REF:-9fa1196}
PY=${PY:-python3}
cd /opt/jev/app

if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
    echo "TradingAgents Python 3.11+ ister; $("$PY" --version). PY=/usr/bin/python3.12 gibi verin." >&2
    exit 1
fi
if [ ! -f /etc/jev/ajan.env ]; then
    install -d -m 700 -o root -g root /etc/jev
    install -o root -g root -m 600 deploy/ajan.env.example /etc/jev/ajan.env
    echo '/etc/jev/ajan.env olusturuldu: API anahtarini doldurup betigi yeniden calistirin.' >&2
    exit 1
fi
chown root:root /etc/jev/ajan.env && chmod 600 /etc/jev/ajan.env
if ! grep -Eq '^(ANTHROPIC|OPENAI|GOOGLE|OPENROUTER|DEEPSEEK)_API_KEY=.+' /etc/jev/ajan.env; then
    echo '/etc/jev/ajan.env icinde dolu bir model API anahtari yok.' >&2
    exit 1
fi

install -d -o jev -g jev -m 750 /var/lib/jev/ajan /var/lib/jev/ajan/ev /var/lib/jev/ajan/ta
if [ ! -d /opt/jev/tradingagents/.git ]; then
    install -d -o jev -g jev /opt/jev/tradingagents
    runuser -u jev -- git clone -q "$TA_REPO" /opt/jev/tradingagents
fi
runuser -u jev -- git -C /opt/jev/tradingagents fetch -q origin
runuser -u jev -- git -C /opt/jev/tradingagents checkout -q "$TA_REF"
[ -d /opt/jev/ajan-venv ] || runuser -u jev -- "$PY" -m venv /opt/jev/ajan-venv
runuser -u jev -- /opt/jev/ajan-venv/bin/python -m pip install -q /opt/jev/tradingagents /opt/jev/app

cp deploy/jev-ajan.service deploy/jev-ajan.timer /etc/systemd/system/
systemctl daemon-reload
echo 'Ilk deneme (dunku gun, BTC+ETH) basliyor; birkac dakika surebilir...'
systemctl start jev-ajan.service || true
journalctl -u jev-ajan.service -n 20 --no-pager || true
runuser -u jev -- /opt/jev/ajan-venv/bin/python -m jev.ajan_kurulu ozet --dir /var/lib/jev/ajan | head -30
systemctl enable --now jev-ajan.timer
systemctl list-timers jev-ajan.timer --no-pager
echo 'Ajan kurulu kuruldu (golge mod, emir yok). Sonuclar jev-sonuc ile son/ajan/ altina yayinlanir.'
