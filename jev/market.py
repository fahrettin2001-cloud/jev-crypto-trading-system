"""Binance Global salt okunur ortalama fiyatı; emir ve kimlik doğrulama içermez."""
import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, DecimalException
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, HTTPRedirectHandler, Request


class MarketDataError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise MarketDataError('Beklenmeyen piyasa API yönlendirmesi')


@dataclass(frozen=True)
class PriceObservation:
    symbol: str
    price: Decimal
    observed_at: datetime
    received_at: datetime
    source: str = 'Binance Global avgPrice'
    average_minutes: int = 5


def fetch_average_price(symbol, *, max_age=timedelta(seconds=30), opener=None, clock=None):
    if not isinstance(symbol, str) or not re.fullmatch(r'[A-Z0-9]{2,30}', symbol):
        raise MarketDataError('Sembol büyük harf/rakam olmalı; örnek BTCUSDT')
    if not isinstance(max_age, timedelta) or max_age <= timedelta(0):
        raise MarketDataError('Fiyat yaşı pozitif timedelta olmalı')
    client = opener if opener is not None else build_opener(NoRedirect())
    url = 'https://data-api.binance.vision/api/v3/avgPrice?symbol=' + symbol
    try:
        with client.open(Request(url, headers={'Accept': 'application/json'}), timeout=10) as response:
            data = response.read(65537)
        if len(data) > 65536:
            raise MarketDataError('Piyasa yanıtı boyut sınırını aştı')
        payload = json.loads(data)
        price = Decimal(payload['price'])
        close = payload['closeTime']
        minutes = payload['mins']
        if (not price.is_finite() or price <= 0 or type(close) is not int or close <= 0
                or type(minutes) is not int or minutes < 0):
            raise MarketDataError('Geçersiz piyasa fiyatı/zamanı')
        observed = datetime.fromtimestamp(close / 1000, tz=timezone.utc)
        now = clock() if clock is not None else datetime.now(timezone.utc)
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise MarketDataError('Geçersiz kontrol saati')
        age = now.astimezone(timezone.utc) - observed
        if age < timedelta(0) or age > max_age:
            raise MarketDataError('Piyasa verisi eski veya gelecekte')
        return PriceObservation(symbol, price, observed, now, average_minutes=minutes)
    except HTTPError as exc:
        retry = exc.headers.get('Retry-After')
        raise MarketDataError(f'Piyasa HTTP hatası {exc.code}; Retry-After={retry}') from exc
    except (URLError, OSError, KeyError, TypeError, ValueError, DecimalException, OverflowError) as exc:
        if isinstance(exc, MarketDataError):
            raise
        raise MarketDataError('Piyasa verisi alınamadı veya doğrulanamadı') from exc


def main():
    parser = argparse.ArgumentParser(description='Binance Global ortalama fiyatı (gerçek emir yok)')
    parser.add_argument('symbol')
    parser.add_argument('--max-age-seconds', type=int, default=30, help='Örnek güncellik sınırı')
    args = parser.parse_args()
    try:
        quote = fetch_average_price(args.symbol, max_age=timedelta(seconds=args.max_age_seconds))
        print(json.dumps({'symbol': quote.symbol, 'price': str(quote.price),
            'observed_at': quote.observed_at.isoformat(), 'source': quote.source,
            'average_minutes': quote.average_minutes}, indent=2))
    except MarketDataError as exc:
        parser.exit(1, f'Hata: {exc}\n')


if __name__ == '__main__':
    main()
