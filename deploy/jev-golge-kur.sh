#!/usr/bin/env bash
# Jev gölge modunu Hostinger sunucusunda kurar (root olarak, anahtar sahibi çalıştırır).
# İşlem kararlarını DEĞİŞTİRMEZ; yalnızca olasılık kaydı yazar. Ayrıntı: docs/JEV-GOLGE-CANLI.md
#
#   bash /opt/jev/app/deploy/jev-golge-kur.sh kur      # ortam + anahtar + ayar (anahtarı sorar)
#   bash /opt/jev/app/deploy/jev-golge-kur.sh dene     # tek ücretli deneme çağrısı
#   bash /opt/jev/app/deploy/jev-golge-kur.sh kapat    # gölge modu kapat (anahtar silinmez)
#   bash /opt/jev/app/deploy/jev-golge-kur.sh kaldir   # eki ve anahtar dosyasını sil
set -euo pipefail

APP=/opt/jev/app
VENV=/opt/jev/venv
STATE=/var/lib/jev/canli
ENV_FILE=/etc/jev/typesafe.env
DROPIN_DIR=/etc/systemd/system/jev-live.service.d
SDK_VERSION=${SDK_VERSION:-0.7.5}

[ "$(id -u)" = 0 ] || { echo "root olarak çalıştırın"; exit 1; }

case "${1:-}" in
kur)
    if [ ! -x "$VENV/bin/python" ]; then
        python3 -m venv "$VENV" 2>/dev/null || {
            echo "python3-venv gerekli: apt-get install -y python3-venv  ardından tekrar çalıştırın"; exit 1; }
    fi
    "$VENV/bin/pip" install -q --disable-pip-version-check "typesafe-sdk==$SDK_VERSION"
    install -d -m 700 -o root -g root /etc/jev
    if [ ! -s "$ENV_FILE" ]; then
        echo "TypeSafe API anahtarını yapıştırıp Enter'a basın (ekranda görünmez):"
        read -rs KEY; echo
        [ -n "$KEY" ] || { echo "Anahtar boş; çıkıldı"; exit 1; }
        umask 077
        printf 'TYPESAFE_API_KEY=%s\n' "$KEY" > "$ENV_FILE"
        unset KEY
        chmod 600 "$ENV_FILE"
        echo "Anahtar $ENV_FILE dosyasına yazıldı (yalnızca root okuyabilir)."
    else
        echo "Anahtar dosyası zaten var: $ENV_FILE (değiştirmek için önce 'kaldir')."
    fi
    if [ ! -f "$STATE/jev_golge.json" ]; then
        cat > "$STATE/jev_golge.json" <<'JSON'
{
  "etkin": true,
  "ufuk_bar": 24,
  "her_n_bar": 4,
  "gunluk_cagri_siniri": 24,
  "zaman_asimi_sn": 30,
  "gecmis_bar": 72,
  "model": "jev-latest"
}
JSON
        chown jev:jev "$STATE/jev_golge.json"
    fi
    install -d -m 755 "$DROPIN_DIR"
    install -m 644 "$APP/deploy/jev-golge.conf" "$DROPIN_DIR/jev-golge.conf"
    systemctl daemon-reload
    echo "Kuruldu. Bir sonraki saatlik çalışmadan itibaren gölge tahminler golge.jsonl'a yazılır."
    echo "Bağlantıyı denemek için (1 ücretli çağrı): bash $0 dene"
    ;;
dene)
    set -a; . "$ENV_FILE"; set +a
    cd "$APP"
    sudo -u jev --preserve-env=TYPESAFE_API_KEY "$VENV/bin/python" -m jev.live golge-dene --dir "$STATE"
    ;;
kapat)
    sudo -u jev "$VENV/bin/python" - "$STATE/jev_golge.json" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p)); d["etkin"] = False
json.dump(d, open(p, "w"), indent=2)
print("Gölge mod kapatıldı (etkin: false).")
PY
    ;;
kaldir)
    rm -f "$DROPIN_DIR/jev-golge.conf" "$ENV_FILE"
    systemctl daemon-reload
    echo "Ek ve anahtar dosyası silindi; bot gölge mod olmadan çalışmaya devam eder."
    ;;
*)
    sed -n '2,10p' "$0"; exit 1 ;;
esac
