import base64
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jev.backup import create_key
from jev.live_backup import backup_live,restore_live,state_lock,MAGIC


@unittest.skipUnless(os.name=='posix','Canlı bot flock kullanır')
class LiveBackupTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.source=self.root/'live';self.source.mkdir()
        (self.source/'ayarlar.json').write_text('{"cash":"500"}')
        (self.source/'durum.pkl').write_bytes(b'not executed as pickle')
        (self.source/'islemler.csv').write_text('zaman,sembol\n')
        (self.source/'DURDUR').write_bytes(b'')
        self.key=self.root/'key.jevkey';create_key(self.key)
        self.archive=self.root/'live.jevbackup';self.dest=self.root/'restored'

    def test_restore_preserves_every_byte_and_stop_file_without_unpickling(self):
        backup_live(self.source,self.archive,self.key)
        with patch('pickle.load',side_effect=AssertionError('must not unpickle')):
            restore_live(self.archive,self.dest,self.key)
        for name in ('ayarlar.json','durum.pkl','islemler.csv','DURDUR'):
            self.assertEqual((self.source/name).read_bytes(),(self.dest/name).read_bytes())
            self.assertEqual((self.dest/name).stat().st_mode & 0o777,0o600)
        self.assertEqual(self.dest.stat().st_mode & 0o777,0o700)

    def test_existing_live_lock_prevents_inconsistent_backup(self):
        from jev.live import _locked
        with _locked(self.source):
            with self.assertRaises(ValueError):backup_live(self.source,self.archive,self.key)
        self.assertFalse(self.archive.exists())

    def test_wrong_key_and_tampering_never_create_restore_directory(self):
        backup_live(self.source,self.archive,self.key)
        wrong=self.root/'wrong.jevkey';create_key(wrong)
        with self.assertRaises(ValueError):restore_live(self.archive,self.dest,wrong)
        data=bytearray(self.archive.read_bytes());data[-1]^=1;self.archive.write_bytes(data)
        with self.assertRaises(ValueError):restore_live(self.archive,self.dest,self.key)
        self.assertFalse(self.dest.exists())

    def test_never_overwrites_or_follows_symlinks(self):
        backup_live(self.source,self.archive,self.key)
        before=self.archive.read_bytes()
        with self.assertRaises(FileExistsError):backup_live(self.source,self.archive,self.key)
        self.assertEqual(self.archive.read_bytes(),before)
        self.dest.mkdir();(self.dest/'keep').write_text('keep')
        with self.assertRaises(FileExistsError):restore_live(self.archive,self.dest,self.key)
        (self.source/'durum.pkl').unlink();(self.source/'durum.pkl').symlink_to(self.key)
        with self.assertRaises(OSError):backup_live(self.source,self.root/'other',self.key)

    def test_missing_or_unknown_source_file_is_not_silently_ignored(self):
        (self.source/'.env').write_text('do not include')
        with self.assertRaises(ValueError):backup_live(self.source,self.archive,self.key)
        (self.source/'.env').unlink();(self.source/'durum.pkl').unlink()
        with self.assertRaises(ValueError):backup_live(self.source,self.archive,self.key)

    def test_authenticated_archive_cannot_escape_destination(self):
        manifest={'version':1,'created_at':'now','files':{'../escape':{'data':'','sha256':hashlib.sha256(b'').hexdigest()}}}
        nonce=os.urandom(12)
        self.archive.write_bytes(MAGIC+nonce+AESGCM(self.key.read_bytes()).encrypt(nonce,json.dumps(manifest).encode(),MAGIC))
        with self.assertRaises(ValueError):restore_live(self.archive,self.dest,self.key)
        self.assertFalse(self.dest.exists())

    def test_failed_restore_cleans_only_new_directory(self):
        backup_live(self.source,self.archive,self.key)
        with patch('jev.live_backup.write_new',side_effect=OSError('disk failed')):
            with self.assertRaises(OSError):restore_live(self.archive,self.dest,self.key)
        self.assertFalse(self.dest.exists());self.assertTrue(self.source.exists())

    def test_real_live_state_restores_and_resumes_identically(self):
        from tests.test_live import FakeBinance,settings,HOUR
        from jev.live import init,run_once,_load
        from datetime import timedelta
        source=self.root/'real-live'
        fake=FakeBinance()
        fake.now=fake.candles['BTCUSDT'][40][0]+timedelta(minutes=2)
        init(source,settings(),fetch=fake,clock=lambda:fake.now)
        backup_live(source,self.archive,self.key)
        restore_live(self.archive,self.dest,self.key)
        self.assertEqual(_load(source).sim.portfolio,_load(self.dest).sim.portfolio)
        fake.now+=HOUR
        first=run_once(source,fetch=fake,clock=lambda:fake.now)
        second=run_once(self.dest,fetch=fake,clock=lambda:fake.now)
        self.assertEqual(first,second)
        for name in ('islemler.csv','redler.csv','varlik_egrisi.csv'):
            if (source/name).exists():
                self.assertEqual((source/name).read_bytes(),(self.dest/name).read_bytes())
