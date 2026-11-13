#!/usr/bin/env bash
# Canlı sanal işlem sonuçlarını ayrı sonuç deposuna yayınlar (jev kullanıcısı olarak).
# Zamanlayıcı: deploy/jev-sonuc.timer. Gizli bilgi içermez: yalnızca sanal işlem
# kayıtları ve durum raporu. Ana kod deposuna yazma yetkisi yoktur.
set -euo pipefail

STATE_DIR=${STATE_DIR:-/var/lib/jev/canli}
APP_DIR=${APP_DIR:-/opt/jev/app}
OUT_DIR=${OUT_DIR:-/var/lib/jev/sonuc-deposu}
KEY=${KEY:-/opt/jev/.ssh/sonuc_key}
KNOWN_HOSTS=${KNOWN_HOSTS:-/opt/jev/.ssh/known_hosts}
PYTHON=${PYTHON:-python3}

if [ -z "${GIT_SSH_COMMAND:-}" ]; then
    export GIT_SSH_COMMAND="ssh -i $KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$KNOWN_HOSTS"
fi

cd "$OUT_DIR"
git pull -q --ff-only 2>/dev/null || true   # boş depo ya da ilk yayın

mkdir -p son
for f in islemler.csv kararlar.jsonl varlik_egrisi.csv redler.csv ayarlar.json; do
    if [ -f "$STATE_DIR/$f" ]; then
        cp "$STATE_DIR/$f" "son/$f"
    fi
done
if [ -f "$STATE_DIR/gunluk.log" ]; then
    tail -n 300 "$STATE_DIR/gunluk.log" > son/gunluk-son.log
fi
(cd "$APP_DIR" && "$PYTHON" -m jev.live status --dir "$STATE_DIR") > son/durum.txt 2>&1 || true
{
    echo "yayin_zamani_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "kod_surumu: $(git -C "$APP_DIR" rev-parse --short HEAD 2>/dev/null || echo bilinmiyor)"
    echo "zamanlayici: $(systemctl is-active jev-live.timer 2>/dev/null || echo bilinmiyor)"
    echo "durdur_dosyasi: $([ -e "$STATE_DIR/DURDUR" ] && echo var || echo yok)"
    echo "disk_kullanimi: $(df -h / | awk 'NR==2 {print $5}')"
} > son/sunucu.txt

if [ ! -f README.md ]; then
    cat > README.md <<'EOF'
# Jev canlı sanal işlem sonuçları

Hostinger sunucusundaki canlı **sanal** işlem botunun (gerçek emir yok, sahte para)
sonuçları. Sunucu her gün `son/` klasörünü günceller. Kod:
https://github.com/fahrettin2001-cloud/jev-crypto-trading-system (`jev.live`).

- `son/durum.txt` — performans ve karar isabeti raporu
- `son/islemler.csv`, `son/kararlar.jsonl`, `son/varlik_egrisi.csv`, `son/redler.csv`
- `son/gunluk-son.log` — son çalışmaların özeti ve uyarılar
- `son/sunucu.txt` — yayın zamanı, kod sürümü, zamanlayıcı ve durdurma durumu
EOF
fi

git add -A
if git diff --cached --quiet; then
    echo "Değişiklik yok"
    exit 0
fi
git commit -q -m "Canlı sanal işlem sonuçları $(date -u +%Y-%m-%d\ %H:%M) UTC"
git push -q origin HEAD:main
echo "Yayınlandı"
