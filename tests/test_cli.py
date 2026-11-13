import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest


class CLITests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'account.db'
        self.risk = Path(temp.name) / 'risk.json'
        self.risk.write_text('{}')

    def run_cli(self, *args, ok=True):
        if args and args[0] == 'init' and '--risk' not in args:
            args = (*args, '--risk', str(self.risk))
        result = subprocess.run([sys.executable, '-m', 'jev', '--db', str(self.path), *args],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0 if ok else 1, result.stderr)
        if not ok:
            self.assertIn('Hata:', result.stderr)
            self.assertNotIn('Traceback', result.stderr)
        return result

    def trade(self, side, *args, ok=True):
        return self.run_cli(side, 'BTCUSDT', *args, '--risk', str(self.risk), ok=ok)

    def test_full_workflow_across_processes(self):
        self.run_cli('init', '10000', '--maker-rate', '0.0005')
        bought = json.loads(self.trade('buy', '0.1', '50000', '--maker').stdout)
        self.assertEqual(bought['fee'], '2.50000')
        self.trade('sell', '0.04', '55000')
        status = json.loads(self.run_cli('status').stdout)
        self.assertEqual(status['cash'], '7195.30000')
        self.assertEqual(status['positions']['BTCUSDT']['quantity'], '0.06')
        history = json.loads(self.run_cli('history').stdout)
        self.assertEqual([t['side'] for t in history], ['BUY', 'SELL'])
        self.assertEqual(history[0]['fee'], bought['fee'])

    def test_init_never_overwrites_existing_file(self):
        self.run_cli('init', '1000')
        before = self.path.read_bytes()
        self.run_cli('init', '9000', ok=False)
        self.assertEqual(self.path.read_bytes(), before)

    def test_missing_account_not_created(self):
        self.run_cli('status', ok=False)
        self.assertFalse(self.path.exists())
        self.trade('buy', '1', '100', ok=False)
        self.assertFalse(self.path.exists())

    def test_risk_rejection_and_insufficient_cash_are_atomic(self):
        self.run_cli('init', '1000')
        before = self.run_cli('status').stdout
        for limits in ({'min_cash_reserve': '950'}, {'max_position_notional': '50'},
                       {'max_trade_notional': '50'}, {'allowed_symbols': ['ETHUSDT']}):
            self.risk.write_text(json.dumps(limits))
            version = json.loads(self.run_cli('risk-show').stdout)['risk_version']
            self.run_cli('risk-set', '--risk', str(self.risk), '--expected-version', str(version))
            self.trade('buy', '1', '100', ok=False)
            self.assertEqual(self.run_cli('status').stdout, before)
        self.risk.write_text('{}')
        self.trade('buy', '100', '100', ok=False)
        self.assertEqual(json.loads(self.run_cli('history').stdout), [])

    def test_price_freshness_rejection(self):
        self.run_cli('init', '1000')
        self.risk.write_text('{"max_price_age_seconds":30}')
        self.run_cli('risk-set', '--risk', str(self.risk), '--expected-version', '1')
        self.trade('buy', '1', '100', ok=False)
        self.trade('buy', '1', '100', '--price-observed-at', '2000-01-01T00:00:00+00:00', ok=False)
        self.assertEqual(json.loads(self.run_cli('history').stdout), [])

    def test_bad_policy_and_input_errors_leave_account_unchanged(self):
        self.run_cli('init', '1000')
        for text in ('{', '[]', '{"typo": 1}', '{"allowed_symbols":"BTCUSDT"}',
                     '{"max_price_age_seconds":"Infinity"}'):
            self.risk.write_text(text)
            self.trade('buy', '1', '100', ok=False)
        self.risk.write_text('{}')
        self.trade('buy', 'NaN', '100', ok=False)
        self.trade('buy', '1', '100', '--price-observed-at', 'bad', ok=False)
        self.assertEqual(json.loads(self.run_cli('history').stdout), [])

    def test_incompatible_database_not_modified(self):
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE unrelated (value TEXT)')
        before = self.path.read_bytes()
        self.run_cli('status', ok=False)
        self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_initial_values_do_not_create_file(self):
        for value in ('NaN', 'Infinity', '-1'):
            self.run_cli('init', value, ok=False)
            self.assertFalse(self.path.exists())
