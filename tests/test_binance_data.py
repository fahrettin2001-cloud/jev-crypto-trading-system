"""Ağ kullanmadan: sahte fetch ile indirme aracının doğrulama adımları."""
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from jev.binance_data import (DownloadError, download_exchange_info, download_month,
                              months_between, VISION)
from jev.exchange_rules import SAMPLE_EXCHANGE_INFO, ExchangeRules

ROW = "1767225600000,100,101,99,100.5,10,1767229199999,1005,5,1,100,0\n"


def make_zip(member, content=ROW):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(member, content)
    return buf.getvalue()


class FakeNet:
    def __init__(self, files):
        self.files, self.calls = files, []

    def __call__(self, url):
        self.calls.append(url)
        if url not in self.files:
            raise DownloadError(f"{url}: HTTP 404")
        return self.files[url]


def month_files(name="BTCUSDT-1h-2026-10", blob=None, checksum=None):
    blob = blob if blob is not None else make_zip(f"{name}.csv")
    digest = checksum or hashlib.sha256(blob).hexdigest()
    url = f"{VISION}/BTCUSDT/1h/{name}.zip"
    return {url: blob, url + ".CHECKSUM": f"{digest}  {name}.zip\n".encode()}


class MonthDownloadTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def test_verified_download_writes_csv(self):
        path = download_month("BTCUSDT", "1h", "2026-10", self.dir, FakeNet(month_files()))
        self.assertEqual(path.name, "BTCUSDT-1h-2026-10.csv")
        self.assertEqual(path.read_text(), ROW)

    def test_checksum_mismatch_writes_nothing(self):
        net = FakeNet(month_files(checksum="0" * 64))
        with self.assertRaisesRegex(DownloadError, "SHA-256"):
            download_month("BTCUSDT", "1h", "2026-10", self.dir, net)
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_unexpected_zip_member_rejected(self):
        net = FakeNet(month_files(blob=make_zip("../../evil.csv")))
        with self.assertRaisesRegex(DownloadError, "beklenmeyen"):
            download_month("BTCUSDT", "1h", "2026-10", self.dir, net)

    def test_unparseable_csv_not_kept(self):
        net = FakeNet(month_files(blob=make_zip("BTCUSDT-1h-2026-10.csv", "bozuk\n")))
        with self.assertRaises(ValueError):
            download_month("BTCUSDT", "1h", "2026-10", self.dir, net)
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_missing_month_raises(self):
        with self.assertRaisesRegex(DownloadError, "404"):
            download_month("BTCUSDT", "1h", "2026-10", self.dir, FakeNet({}))

    def test_existing_file_skipped_unless_forced(self):
        net = FakeNet(month_files())
        download_month("BTCUSDT", "1h", "2026-10", self.dir, net)
        n = len(net.calls)
        download_month("BTCUSDT", "1h", "2026-10", self.dir, net)
        self.assertEqual(len(net.calls), n)
        download_month("BTCUSDT", "1h", "2026-10", self.dir, net, force=True)
        self.assertGreater(len(net.calls), n)

    def test_input_validation(self):
        for args in (("btc/../x", "1h", "2026-10"), ("BTCUSDT", "7h", "2026-10"),
                     ("BTCUSDT", "1h", "2026-13")):
            with self.assertRaises(ValueError):
                download_month(*args, self.dir, FakeNet({}))


class ExchangeInfoDownloadTests(unittest.TestCase):
    def test_writes_parseable_file_and_falls_back(self):
        sample = json.loads(SAMPLE_EXCHANGE_INFO.read_text(encoding="utf-8"))

        class Net:
            calls = []

            def __call__(self, url):
                self.calls.append(url)
                if url.startswith("https://api.binance.com"):
                    raise DownloadError("403")
                return json.dumps(sample).encode()

        net = Net()
        d = Path(tempfile.mkdtemp())
        path = download_exchange_info(["BTCUSDT", "ETHUSDT"], d, net)
        self.assertEqual(len(net.calls), 2)
        self.assertIn("data-api.binance.vision", net.calls[1])
        self.assertIn("symbols=%5B%22BTCUSDT%22%2C%22ETHUSDT%22%5D", net.calls[0])
        self.assertEqual(ExchangeRules.load(path).symbols(), ["BTCUSDT", "ETHUSDT"])

    def test_missing_symbol_in_response_fails(self):
        with self.assertRaises(DownloadError):
            download_exchange_info(["BTCUSDT"], Path(tempfile.mkdtemp()),
                                   lambda url: b'{"symbols": []}')


class MonthsTests(unittest.TestCase):
    def test_months_between(self):
        self.assertEqual(months_between("2025-11", "2026-02"),
                         ["2025-11", "2025-12", "2026-01", "2026-02"])
        for a, b in (("2026-03", "2026-01"), ("2026-1", "2026-02"), ("2000-01", "2026-01")):
            with self.assertRaises(ValueError):
                months_between(a, b)


if __name__ == "__main__":
    unittest.main()
