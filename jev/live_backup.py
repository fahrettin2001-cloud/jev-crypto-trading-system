"""Canlı sanal bot klasörü için kilitli, şifreli yedek ve yeni klasöre kurtarma."""
import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import uuid

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .backup import MAX_SIZE, read_key, write_new

MAGIC = b'JEVLIVEBACKUP\x01'
FILES = frozenset({'ayarlar.json','durum.pkl','gunluk.log','islemler.csv','redler.csv',
                   'varlik_egrisi.csv','kararlar.jsonl','DURDUR','golge.jsonl',
                   'golge_sonuclar.csv'})
REQUIRED = frozenset({'ayarlar.json','durum.pkl'})


@contextmanager
def state_lock(source):
    # Canlı bot jev.live._locked ile aynı flock dosyasını kullanır.
    if os.name != 'posix':
        raise ValueError('Canlı bot kilitli yedeği POSIX sunucuda çalıştırılmalı')
    import fcntl
    if not source.is_dir() or source.is_symlink():
        raise ValueError('Kaynak gerçek bir durum klasörü olmalı')
    flags = os.O_WRONLY | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(source/'.kilit', flags, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('Bot çalışıyor; yedek daha sonra yeniden denenmeli') from exc
        yield
    finally:
        os.close(fd)


def backup_live(source, destination, key_file):
    source = Path(source)
    records, total = {}, 0
    key = read_key(key_file)
    with state_lock(source):
        entries = {p.name for p in source.iterdir()}
        unexpected = entries - FILES - {'.kilit','durum.pkl.tmp'}
        if unexpected:
            raise ValueError('Durum klasöründe desteklenmeyen dosya/klasör var; kapsam gözden geçirilmeli')
        if not REQUIRED <= entries:
            raise ValueError('Hesap durumu veya ayarlar eksik')
        for name in sorted(entries & FILES):
            flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
            fd = os.open(source/name, flags)
            with os.fdopen(fd,'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size + total > MAX_SIZE:
                    raise ValueError('Yalnızca normal, boyut sınırındaki dosyalar yedeklenir')
                data = stream.read(MAX_SIZE-total+1)
            total += len(data)
            if total > MAX_SIZE:
                raise ValueError('Yedek boyut sınırı aşıldı')
            records[name] = {'data':base64.b64encode(data).decode('ascii'),
                             'sha256':hashlib.sha256(data).hexdigest()}
    manifest = {'version':1,'created_at':datetime.now(timezone.utc).isoformat(),'files':records}
    plain = json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()
    nonce = os.urandom(12)
    write_new(destination,MAGIC+nonce+AESGCM(key).encrypt(nonce,plain,MAGIC))


def restore_live(source, destination, key_file):
    if os.name != 'posix':
        raise ValueError('Canlı bot klasörü POSIX sunucuda geri yüklenmeli')
    source, destination = Path(source),Path(destination)
    if source.stat().st_size > MAX_SIZE*2+65536:
        raise ValueError('Şifreli yedek boyutu sınırın üzerinde')
    blob = source.read_bytes()
    if not blob.startswith(MAGIC) or len(blob) < len(MAGIC)+28:
        raise ValueError('Geçersiz canlı hesap yedeği')
    try:
        offset = len(MAGIC)
        plain = AESGCM(read_key(key_file)).decrypt(blob[offset:offset+12],blob[offset+12:],MAGIC)
    except InvalidTag as exc:
        raise ValueError('Yanlış anahtar veya değiştirilmiş yedek') from exc
    manifest = json.loads(plain)
    if not isinstance(manifest,dict) or manifest.get('version') != 1:
        raise ValueError('Desteklenmeyen yedek sürümü')
    created_at = manifest.get('created_at')
    if not isinstance(created_at,str) or datetime.fromisoformat(created_at).utcoffset() is None:
        raise ValueError('Yedek oluşturma zamanı geçersiz')
    records = manifest.get('files')
    if not isinstance(records,dict) or not REQUIRED <= records.keys() or records.keys()-FILES:
        raise ValueError('Yedek dosya listesi geçersiz')
    decoded, total = {},0
    for name,record in records.items():
        data = base64.b64decode(record['data'],validate=True)
        total += len(data)
        if total > MAX_SIZE or hashlib.sha256(data).hexdigest() != record['sha256']:
            raise ValueError('Yedek dosyası bütünlük/boyut kontrolü başarısız')
        decoded[name] = data
    if not isinstance(json.loads(decoded['ayarlar.json']),dict):
        raise ValueError('Yedek ayarları geçersiz')
    # Pickle burada asla çalıştırılmaz; yalnızca oluşturduğumuz yeni klasöre yazılır.
    destination.mkdir(mode=0o700)
    try:
        for name,data in decoded.items():
            write_new(destination/name,data)
    except BaseException:
        shutil.rmtree(destination)
        raise
    return manifest['created_at']


def main():
    parser=argparse.ArgumentParser(description='Sanal bot klasörünü şifreli yedekle/geri yükle')
    sub=parser.add_subparsers(dest='command',required=True)
    backup=sub.add_parser('backup')
    backup.add_argument('--dir',required=True,type=Path)
    backup.add_argument('--destination-dir',required=True,type=Path)
    restore=sub.add_parser('restore')
    restore.add_argument('--source',required=True,type=Path)
    restore.add_argument('--destination',required=True,type=Path)
    for command in (backup,restore):
        command.add_argument('--key-file',required=True,type=Path)
    args=parser.parse_args()
    try:
        if args.command=='backup':
            if not args.destination_dir.is_dir():
                raise ValueError('Yedek hedef klasörünü önce oluşturun')
            name=datetime.now(timezone.utc).strftime('jev-live-%Y%m%dT%H%M%S-')+uuid.uuid4().hex[:8]+'.jevbackup'
            destination=args.destination_dir/name
            backup_live(args.dir,destination,args.key_file)
            print('Şifreli yedek oluşturuldu: '+str(destination))
        else:
            date=restore_live(args.source,args.destination,args.key_file)
            print('Yeni klasöre geri yüklendi; yedek zamanı: '+date)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        parser.exit(1,f'Hata: {exc}\n')


if __name__=='__main__':
    main()
