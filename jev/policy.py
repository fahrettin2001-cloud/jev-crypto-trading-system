"""Risk politikasının kayıpsız, sürümlenebilir JSON gösterimi."""
from datetime import timedelta
from decimal import Decimal
import json

from .risk import RiskLimits


def policy_dict(risk):
    if not isinstance(risk, RiskLimits):
        raise ValueError('RiskLimits gerekli')
    return {
        'max_trade_notional': _number(risk.max_trade_notional),
        'max_daily_realized_loss': _number(risk.max_daily_realized_loss),
        'max_total_position_notional': _number(risk.max_total_position_notional),
        'min_cash_reserve': _number(risk.min_cash_reserve),
        'max_position_notional': _number(risk.max_position_notional),
        'allowed_symbols': sorted(risk.allowed_symbols) if risk.allowed_symbols is not None else None,
        'max_price_age_seconds': (str(Decimal(risk.max_price_age.days * 86400
            + risk.max_price_age.seconds) + Decimal(risk.max_price_age.microseconds) / 1000000)
            if risk.max_price_age is not None else None),
    }


def _number(value):
    return str(value) if value is not None else None


def parse_policy(data):
    names = {'max_trade_notional', 'min_cash_reserve', 'max_position_notional',
             'allowed_symbols', 'max_price_age_seconds', 'max_daily_realized_loss',
             'max_total_position_notional'}
    if not isinstance(data, dict) or data.keys() - names:
        raise ValueError('Risk politikası desteklenen alanlardan oluşan JSON nesnesi olmalı')
    data = dict(data)
    symbols = data.get('allowed_symbols')
    if symbols is not None and (not isinstance(symbols, list)
            or any(not isinstance(s, str) or not s.strip() for s in symbols)):
        raise ValueError('allowed_symbols boş olmayan sembollerden oluşan liste olmalı')
    for key, value in data.items():
        if key != 'allowed_symbols' and value is not None and (isinstance(value, bool)
                or not isinstance(value, (str, int, float, Decimal))):
            raise ValueError(f'Geçersiz sayısal risk alanı: {key}')
    seconds = data.pop('max_price_age_seconds', None)
    if seconds is not None:
        seconds = Decimal(str(seconds))
        micros = seconds * 1000000
        if not seconds.is_finite() or seconds <= 0 or micros != micros.to_integral_value():
            raise ValueError('Fiyat yaşı pozitif ve mikrosaniye hassasiyetinde olmalı')
        data['max_price_age'] = timedelta(microseconds=int(micros))
    return RiskLimits(**data)


def encode_policy(risk):
    return json.dumps(policy_dict(risk), sort_keys=True, separators=(',', ':'))


def decode_policy(text):
    data = json.loads(text, parse_float=Decimal)
    # Saklanan politikada eksik alanlar bozulma olarak kabul edilir.
    expected = policy_dict(RiskLimits()).keys()
    old = expected - {'max_daily_realized_loss', 'max_total_position_notional'}
    if not isinstance(data, dict) or data.keys() not in (expected, old):
        raise ValueError('Eksik veya desteklenmeyen kayıtlı risk politikası')
    return parse_policy(data)
