"""Kayıtlı sanal hesabın masraf ve risk ayarlarıyla birlikte raporu."""
from dataclasses import asdict
from decimal import Decimal

from .policy import policy_dict
from .risk import RiskError


def account_report(account):
    p = account.portfolio
    try:
        version, limits = account.policy_status()
        policy = {'version': version, 'limits': policy_dict(limits), 'error': None}
    except RiskError as exc:
        policy = {'version': None, 'limits': None, 'error': str(exc)}
    return {'mode': 'paper', 'cash': str(p.cash), 'initial_cash': str(p.initial_cash),
            'quote': p.quote, 'positions': {s: {k:str(v) for k,v in asdict(pos).items()}
                                         for s,pos in p.positions.items()},
            'trade_count': len(p.trades), 'total_fees': str(p.total_fees),
            'realized_pnl': str(p.realized_pnl), 'policy': policy}
