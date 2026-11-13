from pathlib import Path
import sqlite3
import tempfile
import unittest

from jev import RiskError, RiskLimits, SQLitePortfolio
from jev.backup import create_key, encrypted_backup, restore_backup


class BackupTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.key, self.backup = self.folder/'key.jevkey', self.folder/'backup.jevbackup'
        create_key(self.key)
        self.account = SQLitePortfolio(self.folder/'account.db', initial_cash=1000,
                                       risk=RiskLimits(max_trade_notional=500))
        self.addCleanup(self.account.close)

    def test_restore_preserves_wal_state_policy_history_and_trading(self):
        self.account._db.execute('PRAGMA journal_mode=WAL')
        self.account.buy('BTCUSDT', 1, 100)
        expected = self.account.portfolio
        encrypted_backup(self.account, self.backup, self.key)
        self.assertFalse(self.backup.read_bytes().startswith(b'SQLite'))
        self.account.buy('BTCUSDT', 1, 100)
        restored = self.folder/'restored.db'
        restore_backup(self.backup, restored, self.key)
        with SQLitePortfolio.open(restored) as account:
            self.assertEqual(account.portfolio, expected)
            self.assertEqual(account.risk, self.account.risk)
            with self.assertRaises(RiskError):
                account.buy('BTCUSDT', 1, 600)
            account.sell('BTCUSDT', 1, 100)
            self.assertEqual(len(account.portfolio.trades), 2)
            self.assertEqual(account._db.execute('SELECT risk_version FROM trades LIMIT 1').fetchone()[0], 1)

    def test_wrong_key_or_tampering_never_creates_destination(self):
        encrypted_backup(self.account, self.backup, self.key)
        wrong = self.folder/'wrong.jevkey'
        create_key(wrong)
        dest = self.folder/'restored.db'
        with self.assertRaises(ValueError):
            restore_backup(self.backup, dest, wrong)
        self.assertFalse(dest.exists())
        damaged = bytearray(self.backup.read_bytes())
        damaged[-1] ^= 1
        self.backup.write_bytes(damaged)
        with self.assertRaises(ValueError):
            restore_backup(self.backup, dest, self.key)
        self.assertFalse(dest.exists())

    def test_existing_files_never_overwritten(self):
        encrypted_backup(self.account, self.backup, self.key)
        before = self.backup.read_bytes()
        with self.assertRaises(FileExistsError):
            encrypted_backup(self.account, self.backup, self.key)
        self.assertEqual(self.backup.read_bytes(), before)
        with self.assertRaises(FileExistsError):
            create_key(self.key)
        dest = self.folder/'existing.db'
        dest.write_bytes(b'keep')
        with self.assertRaises(FileExistsError):
            restore_backup(self.backup, dest, self.key)
        self.assertEqual(dest.read_bytes(), b'keep')

    def test_policy_missing_backup_cannot_enable_trading(self):
        with SQLitePortfolio(self.folder/'legacy.db', initial_cash=1000) as legacy:
            encrypted_backup(legacy, self.backup, self.key)
        dest = self.folder/'restored.db'
        restore_backup(self.backup, dest, self.key)
        with SQLitePortfolio.open(dest) as restored:
            with self.assertRaises(RiskError):
                restored.buy('BTCUSDT', 1, 100)
