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
for f in islemler.csv kararlar.jsonl varlik_egrisi.csv redler.csv ayarlar.json \
         golge.jsonl jev_golge.json; do
    if [ -f "$STATE_DIR/$f" ]; then
        cp "$STATE_DIR/$f" "son/$f"
    fi
done
if [ -f "$STATE_DIR/gunluk.log" ]; then
    tail -n 300 "$STATE_DIR/gunluk.log" > son/gunluk-son.log
fi
(cd "$APP_DIR" && "$PYTHON" -m jev.live status --dir "$STATE_DIR") > son/durum.txt 2>&1 || true
(cd "$APP_DIR" && "$PYTHON" -m jev.live golge --dir "$STATE_DIR" --csv "$OUT_DIR/son/golge_sonuclar.csv") \
    > son/golge.txt 2>&1 || true

# Ajan kurulu (TradingAgents, gölge mod) çıktıları — kuruluysa. Gizli bilgi içermez.
AJAN_DIR=${AJAN_DIR:-/var/lib/jev/ajan}
if [ -f "$AJAN_DIR/ajan_kararlar.jsonl" ]; then
    mkdir -p son/ajan/raporlar
    cp "$AJAN_DIR/ajan_kararlar.jsonl" son/ajan/
    [ -f "$AJAN_DIR/ozet.md" ] && cp "$AJAN_DIR/ozet.md" son/ajan/
    [ -f "$AJAN_DIR/gunluk.log" ] && tail -n 200 "$AJAN_DIR/gunluk.log" > son/ajan/gunluk-son.log
    # Son 14 günün raporları
    find "$AJAN_DIR/raporlar" -name '*.md' -mtime -14 -exec cp -p {} son/ajan/raporlar/ \; 2>/dev/null || true
    find son/ajan/raporlar -name '*.md' -mtime +14 -delete 2>/dev/null || true
fi
# Trend topluluğu (ikinci sanal hesap, günlük mum) — kuruluysa.
TREND_DIR=${TREND_DIR:-/var/lib/jev/trend}
if [ -f "$TREND_DIR/durum.pkl" ]; then
    mkdir -p son/trend
    for f in islemler.csv kararlar.jsonl varlik_egrisi.csv redler.csv ayarlar.json; do
        if [ -f "$TREND_DIR/$f" ]; then cp "$TREND_DIR/$f" son/trend/; fi
    done
    if [ -f "$TREND_DIR/gunluk.log" ]; then tail -n 200 "$TREND_DIR/gunluk.log" > son/trend/gunluk-son.log; fi
    (cd "$APP_DIR" && "$PYTHON" -m jev.live status --dir "$TREND_DIR" --horizon 5) > son/trend/durum.txt 2>&1 || true
    echo "trend_zamanlayici: $(systemctl is-active jev-trend.timer 2>/dev/null || echo bilinmiyor)" > son/trend/sunucu.txt
fi

# Duygu endeksi (bedava; Korku/Açgözlülük + Binance fonlama/long-short) — kuruluysa.
DUYGU_DIR=${DUYGU_DIR:-/var/lib/jev/duygu}
if [ -f "$DUYGU_DIR/duygu_kayit.jsonl" ]; then
    mkdir -p son/duygu
    for f in duygu_kayit.jsonl duygu_ozet.md gecmis_testi.md; do
        if [ -f "$DUYGU_DIR/$f" ]; then cp "$DUYGU_DIR/$f" son/duygu/; fi
    done
fi
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
- `son/golge.txt`, `son/golge.jsonl`, `son/golge_sonuclar.csv` — Jev gölge modu
  (işlemleri etkilemeyen olasılık tahminleri ve isabeti)
- `son/ajan/` — TradingAgents ajan kurulu (gölge mod): `ozet.md`, kararlar, raporlar
- `son/trend/` — ikinci sanal hesap: trend topluluğu (günlük mum); `durum.txt`, işlemler
- `son/duygu/` — duygu endeksi (Korku/Açgözlülük, fonlama, long/short) ve geçmiş testi
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
