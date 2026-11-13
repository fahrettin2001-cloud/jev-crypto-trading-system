"""Çevrimdışı sanal işlem için bağımsız risk kontrolü taslağı."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .fees import D
from .portfolio import TradeError


class RiskError(TradeError):
    """İşlem bağımsız risk kontrolünden geçemedi."""


@dataclass(frozen=True)
class RiskLimits:
    # Ekipçe onaylanmış sayısal limit yoktur; örnek limit açıkça seçilir.
    max_trade_notional: Decimal | None = None
    allowed_symbols: frozenset[str] | None = None

    def __post_init__(self):
        if self.max_trade_notional is not None:
            limit = D(self.max_trade_notional)
            if not limit.is_finite() or limit <= 0:
                raise ValueError("İşlem limiti sonlu ve pozitif olmalı")
            object.__setattr__(self, "max_trade_notional", limit)
        if self.allowed_symbols is not None:
            object.__setattr__(self, "allowed_symbols", frozenset(self.allowed_symbols))

    def check(self, symbol, quantity, price):
        if not isinstance(symbol, str) or not symbol.strip():
            raise RiskError("Sembol boş olamaz")
        try:
            quantity, price = D(quantity), D(price)
            if (not quantity.is_finite() or not price.is_finite()
                    or quantity <= 0 or price <= 0):
                raise RiskError("Miktar ve fiyat sonlu ve pozitif olmalı")
            notional = quantity * price
            if not notional.is_finite():
                raise RiskError("İşlem tutarı sonlu olmalı")
        except (InvalidOperation, OverflowError, TypeError, ValueError) as exc:
            raise RiskError("Geçersiz miktar veya fiyat") from exc
        if self.allowed_symbols is not None and symbol not in self.allowed_symbols:
            raise RiskError("Sembol izin listesinde değil")
        if self.max_trade_notional is not None and notional > self.max_trade_notional:
            raise RiskError("İşlem tutarı örnek risk limitini aşıyor")
        return quantity, price
