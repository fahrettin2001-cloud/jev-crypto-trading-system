#!/usr/bin/env bash
# Canlı sanal işlem sonuçlarını yayınlamak için bir kerelik kurulum.
# root olarak çalıştırın:
#   bash /opt/jev/app/deploy/sonuc-anahtar.sh anahtar
#       -> jev kullanıcısı için yalnızca sonuç deposuna yazacak SSH anahtarı üretir
#          ve açık (public) anahtarı yazdırır. Bunu GitHub'da sonuç deposuna
#          "Deploy key" olarak, "Allow write access" işaretli ekleyin.
#   bash /opt/jev/app/deploy/sonuc-anahtar.sh bagla git@github.com:KULLANICI/jev-canli-sonuclar.git
#       -> sonuç deposunu sunucuya klonlar ve ilk yayını yapar.
set -euo pipefail

SSH_DIR=/opt/jev/.ssh
KEY=$SSH_DIR/sonuc_key
OUT_DIR=/var/lib/jev/sonuc-deposu
# GitHub'ın yayımladığı ed25519 sunucu anahtarı (docs.github.com, "GitHub's SSH key
# fingerprints"). Sabitlendiği için ilk bağlantıda sahte sunucuya güvenilmez.
GITHUB_HOST_KEY='github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl'

if [ "$(id -u)" -ne 0 ]; then
    echo "root olarak çalıştırın" >&2
    exit 1
fi

case "${1:-}" in
anahtar)
    install -d -o jev -g jev -m 700 "$SSH_DIR"
    if [ ! -f "$KEY" ]; then
        sudo -u jev ssh-keygen -q -t ed25519 -N "" -C "jev-canli-sonuc@$(hostname)" -f "$KEY"
    fi
    echo "$GITHUB_HOST_KEY" > "$SSH_DIR/known_hosts"
    chown jev:jev "$SSH_DIR/known_hosts"
    chmod 644 "$SSH_DIR/known_hosts"
    echo
    echo "Aşağıdaki satırı GitHub'da sonuç deposuna Deploy key olarak ekleyin"
    echo "(Settings -> Deploy keys -> Add deploy key, 'Allow write access' işaretli):"
    echo
    cat "$KEY.pub"
    ;;
bagla)
    URL="${2:?Kullanım: $0 bagla git@github.com:KULLANICI/DEPO.git}"
    case "$URL" in
        git@github.com:*/*.git) ;;
        *) echo "Depo adresi git@github.com:KULLANICI/DEPO.git biçiminde olmalı" >&2; exit 1 ;;
    esac
    [ -f "$KEY" ] || { echo "Önce: $0 anahtar" >&2; exit 1; }
    export GIT_SSH_COMMAND="ssh -i $KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$SSH_DIR/known_hosts"
    if [ ! -d "$OUT_DIR/.git" ]; then
        install -d -o jev -g jev "$OUT_DIR"
        sudo -u jev env GIT_SSH_COMMAND="$GIT_SSH_COMMAND" git clone -q "$URL" "$OUT_DIR"
    fi
    sudo -u jev git -C "$OUT_DIR" config user.name "jev-canli-sunucu"
    sudo -u jev git -C "$OUT_DIR" config user.email "jev-canli-sunucu@users.noreply.github.com"
    sudo -u jev bash /opt/jev/app/deploy/sonuc-yayinla.sh
    echo "Bağlandı ve ilk yayın yapıldı: $URL"
    ;;
*)
    sed -n '2,11p' "$0"
    exit 1
    ;;
esac
