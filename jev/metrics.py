"""Backtest performans ölçümleri. Tüm hesaplar Decimal."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Sequence

from .portfolio import Trade

ZERO = Decimal("0")


@dataclass(frozen=True)
class Metrics:
    start: datetime
    end: datetime
    bars: int
    initial_equity: Decimal
    final_equity: Decimal
    total_return: Decimal          # 0.05 = %5
    max_drawdown: Decimal          # 0.10 = zirveden %10 düşüş
    trades: int
    buys: int
    sells: int
    win_rate: Decimal | None       # kârla kapanan satış oranı; satış yoksa None
    realized_pnl: Decimal
    total_fees: Decimal
    fee_ratio: Decimal             # komisyon / başlangıç nakdi


def max_drawdown(values: Sequence[Decimal]) -> Decimal:
    """Zirveden en büyük göreli düşüş (0 ile 1 arası)."""
    peak, worst = None, ZERO
    for v in values:
        if peak is None or v > peak:
            peak = v
        if peak > 0:
            worst = max(worst, (peak - v) / peak)
    return worst


def compute_metrics(equity_curve: Sequence[tuple[datetime, Decimal]], trades: Sequence[Trade],
                    initial_cash: Decimal) -> Metrics:
    if not equity_curve:
        raise ValueError("Varlık eğrisi boş")
    values = [v for _, v in equity_curve]
    sells = [t for t in trades if t.side == "SELL"]
    wins = sum(1 for t in sells if t.realized_pnl > 0)
    fees = sum((t.fee for t in trades), ZERO)
    return Metrics(
        start=equity_curve[0][0],
        end=equity_curve[-1][0],
        bars=len(equity_curve),
        initial_equity=initial_cash,
        final_equity=values[-1],
        total_return=values[-1] / initial_cash - 1,
        max_drawdown=max_drawdown([initial_cash, *values]),
        trades=len(trades),
        buys=len(trades) - len(sells),
        sells=len(sells),
        win_rate=Decimal(wins) / len(sells) if sells else None,
        realized_pnl=sum((t.realized_pnl for t in sells), ZERO),
        total_fees=fees,
        fee_ratio=fees / initial_cash,
    )
