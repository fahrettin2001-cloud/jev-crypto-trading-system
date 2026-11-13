"""AES-256-GCM ile şifreli, SQLite backup API ile tutarlı hesap yedeği."""
import os
from pathlib import Path
import sqlite3
from contextlib import closing
import tempfile

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .storage import SQLitePortfolio

MAGIC = b'JEVBACKUP\x01'
MAX_SIZE = 128 * 1024 * 1024


def write_new(path, data):
    """Mevcut dosyayı ezmeden, yalnızca kullanıcıya açık yeni dosya yaz."""
    path = Path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink()
        raise


def create_key(path):
    write_new(path, AESGCM.generate_key(bit_length=256))


def read_key(path):
    key = Path(path).read_bytes()
    if len(key) != 32:
        raise ValueError('Yedek anahtarı tam 32 bayt olmalı')
    return key


def encrypted_backup(account, destination, key_file):
    key = read_key(key_file)
    with tempfile.TemporaryDirectory(prefix='jev-backup-') as folder:
        snapshot = Path(folder) / 'snapshot.db'
        # SQLite backup API WAL dahil tutarlı anlık görüntüyü alır.
        with closing(sqlite3.connect(snapshot)) as target:
            account._db.backup(target)
        if snapshot.stat().st_size > MAX_SIZE:
            raise ValueError('Hesap yedek boyutu sınırını aşıyor')
        nonce = os.urandom(12)
        payload = AESGCM(key).encrypt(nonce, snapshot.read_bytes(), MAGIC)
        write_new(destination, MAGIC + nonce + payload)


def restore_backup(source, destination, key_file):
    """Doğrula, yeni dosyaya geri yükle; mevcut hesap asla ezilmez."""
    source, destination = Path(source), Path(destination)
    if source.stat().st_size > MAX_SIZE + 1024:
        raise ValueError('Yedek dosyası boyut sınırını aşıyor')
    data = source.read_bytes()
    if not data.startswith(MAGIC) or len(data) < len(MAGIC) + 28:
        raise ValueError('Desteklenmeyen veya eksik yedek dosyası')
    offset = len(MAGIC)
    try:
        plain = AESGCM(read_key(key_file)).decrypt(data[offset:offset+12], data[offset+12:], MAGIC)
    except InvalidTag as exc:
        raise ValueError('Yedek doğrulanamadı: yanlış anahtar veya değiştirilmiş dosya') from exc
    with tempfile.TemporaryDirectory(prefix='jev-restore-') as folder:
        restored = Path(folder) / 'restored.db'
        write_new(restored, plain)
        with closing(sqlite3.connect(restored)) as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('SQLite bütünlük kontrolü başarısız')
        with SQLitePortfolio.open(restored) as account:
            account.portfolio
            # Politikasız eski yedekler okunabilir kalır; işlem katmanı bunları engeller.
            count = account._db.execute('SELECT count(*) FROM risk_policies').fetchone()[0]
            if count:
                account.policy_status()
        write_new(destination, restored.read_bytes())
