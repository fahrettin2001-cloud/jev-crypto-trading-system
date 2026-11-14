"""AES-256-GCM ile şifreli, SQLite backup API ile tutarlı hesap yedeği."""
import os
from pathlib import Path
import sqlite3
from contextlib import closing

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .storage import SQLitePortfolio
from .private_file import private_fd

LEGACY_MAGIC = b'JEVBACKUP\x01'
MAGIC = b'JEVBACKUP\x02'
MAX_SIZE = 128 * 1024 * 1024


def write_new(path, data):
    """Mevcut dosyayı ezmeden, yalnızca kullanıcıya açık yeni dosya yaz."""
    path = Path(path)
    fd = private_fd(path)
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
    with closing(sqlite3.connect(':memory:')) as snapshot:
        snapshot.execute('PRAGMA temp_store=MEMORY')
        account._db.backup(snapshot)
        if snapshot.execute('PRAGMA page_count').fetchone()[0] * snapshot.execute('PRAGMA page_size').fetchone()[0] > MAX_SIZE:
            raise ValueError('Hesap yedek boyutu sınırını aşıyor')
        # iterdump Python 3.10 dahil desteklenir; hiçbir şifresiz geçici dosya yok.
        chunks, size = [], 0
        for line in snapshot.iterdump():
            chunk = (line + '\n').encode('utf-8')
            size += len(chunk)
            if size > MAX_SIZE:
                raise ValueError('Hesap yedek boyutu sınırını aşıyor')
            chunks.append(chunk)
        plain = b''.join(chunks)
    nonce = os.urandom(12)
    payload = AESGCM(key).encrypt(nonce, plain, MAGIC)
    write_new(destination, MAGIC + nonce + payload)


def _restore_in_memory(plain, magic):
    db = sqlite3.connect(':memory:')
    try:
        db.execute('PRAGMA temp_store=MEMORY')
        if magic == LEGACY_MAGIC:
            if not hasattr(db, 'deserialize'):
                raise ValueError('Eski v1 yedeği bellekte açmak için Python 3.11+ gerekli')
            db.deserialize(plain)
            db.execute('PRAGMA temp_store=MEMORY')
        else:
            def authorize(action, arg1, arg2, database, trigger):
                if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
                    return sqlite3.SQLITE_DENY
                if action == sqlite3.SQLITE_PRAGMA:
                    return sqlite3.SQLITE_DENY
                if action == sqlite3.SQLITE_FUNCTION and str(arg2).lower() == 'load_extension':
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            db.set_authorizer(authorize)
            db.executescript(plain.decode('utf-8'))
            db.set_authorizer(None)
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite bütünlük kontrolü başarısız')
        account = SQLitePortfolio.__new__(SQLitePortfolio)
        account._db = db
        account._load()
        account._ensure_policy_schema()
        if db.execute('SELECT count(*) FROM risk_policies').fetchone()[0]:
            account.policy_status()
        return db
    except BaseException:
        db.close()
        raise


def restore_backup(source, destination, key_file):
    """Bellekte doğrula; yalnızca istenen yeni hesap dosyasını yaz."""
    source, destination = Path(source), Path(destination)
    if source.stat().st_size > MAX_SIZE + 1024:
        raise ValueError('Yedek dosyası boyut sınırını aşıyor')
    data = source.read_bytes()
    magic = data[:len(MAGIC)]
    if magic not in (MAGIC, LEGACY_MAGIC) or len(data) < len(MAGIC) + 28:
        raise ValueError('Desteklenmeyen veya eksik yedek dosyası')
    offset = len(magic)
    try:
        plain = AESGCM(read_key(key_file)).decrypt(data[offset:offset+12], data[offset+12:], magic)
    except InvalidTag as exc:
        raise ValueError('Yedek doğrulanamadı: yanlış anahtar veya değiştirilmiş dosya') from exc
    with closing(_restore_in_memory(plain, magic)) as restored:
        fd = private_fd(destination)
        os.close(fd)
        try:
            with closing(sqlite3.connect(destination)) as target:
                restored.backup(target)
        except BaseException:
            destination.unlink()
            raise
