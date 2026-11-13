"""Komisyon hesapları.

Tüm tutarlar Decimal ile tutulur; float yuvarlama hataları para hesabında
kabul edilemez. Komisyon, işlemin karşı para birimi (ör. USDT) cinsinden
alınır. Binance'te komisyon varsayılan olarak alınan varlıktan düşülür; sanal
aşamada hesabı sade tutmak için karşı para birimi kullanıyoruz.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


def D(value) -> Decimal:
    """Değeri Decimal'e çevirir. float'ı str üzerinden çevirerek
    0.1 gibi değerlerin ikili gösterim hatasını taşımasını önler."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(value)


@dataclass(frozen=True)
class FeeSchedule:
    """Maker/taker komisyon oranları (0.001 = %0,1)."""

    maker_rate: Decimal = Decimal("0.001")
    taker_rate: Decimal = Decimal("0.001")

    def __post_init__(self) -> None:
        for name in ("maker_rate", "taker_rate"):
            rate = D(getattr(self, name))
            if not rate.is_finite() or rate < 0 or rate >= 1:
                raise ValueError(f"{name} 0 ile 1 arasında olmalı: {rate}")
            object.__setattr__(self, name, rate)

    def fee(self, notional, taker: bool = True) -> Decimal:
        """İşlem tutarı (miktar x fiyat) için komisyonu döndürür."""
        notional = D(notional)
        if notional < 0:
            raise ValueError("İşlem tutarı negatif olamaz")
        rate = self.taker_rate if taker else self.maker_rate
        return notional * rate
