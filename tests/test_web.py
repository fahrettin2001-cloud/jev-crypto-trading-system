import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from jev import RiskLimits, SQLitePortfolio
from jev.web import make_server


class WebTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name)/'account.db'
        with SQLitePortfolio(self.path, initial_cash=1000, risk=RiskLimits(max_trade_notional=500)) as account:
            account.buy('BTCUSDT', 1, 100)
        self.server = make_server(self.path, 0)
        thread = Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.stop_server, thread)
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def stop_server(self, thread):
        self.server.shutdown()
        self.server.server_close()
        thread.join()

    def test_status_history_and_page(self):
        with urlopen(self.base+'/api/status') as response:
            data = json.load(response)
        self.assertEqual(data['cash'], '899.900')
        self.assertEqual(data['policy']['version'], 1)
        with urlopen(self.base+'/api/history') as response:
            self.assertEqual(json.load(response)[0]['symbol'], 'BTCUSDT')
        with urlopen(self.base) as response:
            self.assertIn('Hesabına genel bakış', response.read().decode())

    def test_unknown_host_and_mutation_rejected(self):
        with self.assertRaises(HTTPError) as caught:
            urlopen(Request(self.base+'/api/status', headers={'Host':'evil.example'}))
        self.assertEqual(caught.exception.code, 403)
        with self.assertRaises(HTTPError) as caught:
            urlopen(Request(self.base+'/api/status', data=b'{}', method='POST'))
        self.assertEqual(caught.exception.code, 501)
        with SQLitePortfolio.open(self.path) as account:
            self.assertEqual(len(account.portfolio.trades), 1)
