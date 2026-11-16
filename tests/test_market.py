from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError

from jev.market import MarketDataError, NoRedirect, fetch_average_price


class MarketTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 13, tzinfo=timezone.utc)
        self.payload = {'price': '50000.12345678', 'mins': 5,
                        'closeTime': int(self.now.timestamp() * 1000)}

    def fetch(self, payload):
        opener = Mock()
        opener.open.return_value = BytesIO(json.dumps(payload).encode())
        result = fetch_average_price('BTCUSDT', opener=opener, clock=lambda: self.now)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, 'https://data-api.binance.vision/api/v3/avgPrice?symbol=BTCUSDT')
        self.assertEqual(request.get_method(), 'GET')
        return result

    def test_official_average_price_response(self):
        result = self.fetch(self.payload)
        self.assertEqual(str(result.price), '50000.12345678')
        self.assertEqual(result.observed_at, self.now)
        self.assertEqual(result.average_minutes, 5)

    def test_bad_or_stale_data_fails_closed(self):
        for update in ({'price': 'NaN'}, {'price': '0'}, {'price': '-1'}, {'closeTime': None},
                       {'closeTime': int((self.now-timedelta(seconds=31)).timestamp()*1000)},
                       {'closeTime': int((self.now+timedelta(seconds=1)).timestamp()*1000)},
                       {'mins': -1}):
            with self.subTest(update=update), self.assertRaises(MarketDataError):
                self.fetch({**self.payload, **update})
        with self.assertRaises(MarketDataError):
            self.fetch({})

    def test_unexpected_symbol_redirect_and_rate_limit(self):
        for symbol in ('btc', '../order', 'BTCUSDT&extra=1'):
            with self.assertRaises(MarketDataError):
                fetch_average_price(symbol)
        with self.assertRaises(MarketDataError):
            NoRedirect().redirect_request(None, None, None, None, None, None)
        opener = Mock()
        opener.open.side_effect = HTTPError('url', 429, 'rate limit', {'Retry-After':'60'}, None)
        with self.assertRaisesRegex(MarketDataError, 'Retry-After=60'):
            fetch_average_price('BTCUSDT', opener=opener)
