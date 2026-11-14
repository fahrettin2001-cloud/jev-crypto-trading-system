"""Çevrimdışı sanal işlem için bağımsız risk kontrolü taslağı."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, DecimalException

from .fees import D
from .portfolio import TradeError


class RiskError(TradeError):
    """İşlem bağımsız risk kontrolünden geçemedi."""


@dataclass(frozen=True)
class RiskLimits:
    # Ekipçe onaylanmış sayısal limit yoktur; örnek limit açıkça seçilir.
    max_trade_notional: Decimal | None = None
    allowed_symbols: frozenset[str] | None = None

    min_cash_reserve: Decimal | None = None
    max_position_notional: Decimal | None = None
    max_price_age: timedelta | None = None
    max_daily_realized_loss: Decimal | None = None
    max_total_position_notional: Decimal | None = None

    def __post_init__(self):
        if self.max_price_age is not None:
            if not isinstance(self.max_price_age, timedelta) or self.max_price_age <= timedelta(0):
                raise ValueError("Fiyat yaşı limiti pozitif timedelta olmalı")
        for name in ("max_trade_notional", "min_cash_reserve", "max_position_notional",
                     "max_daily_realized_loss", "max_total_position_notional"):
            value = getattr(self, name)
            if value is None:
                continue
            try:
                limit = D(value)
                if (not limit.is_finite() or limit < 0
                        or (name != "min_cash_reserve" and limit == 0)):
                    raise ValueError(f"Geçersiz risk limiti: {name}")
            except (DecimalException, TypeError, ValueError) as exc:
                raise ValueError(f"Geçersiz risk limiti: {name}") from exc
            object.__setattr__(self, name, limit)
        if self.max_total_position_notional is not None and self.max_price_age is None:
            raise ValueError("Toplam pozisyon limiti için fiyat yaşı sınırı da gerekli")
        if self.allowed_symbols is not None:
            object.__setattr__(self, "allowed_symbols", frozenset(self.allowed_symbols))

    def check(self, symbol, quantity, price, *, side="BUY"):
        if side not in ("BUY", "SELL"):
            raise RiskError("İşlem yönü BUY veya SELL olmalı")
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
        except (DecimalException, OverflowError, TypeError, ValueError) as exc:
            raise RiskError("Geçersiz miktar veya fiyat") from exc
        if self.allowed_symbols is not None and symbol not in self.allowed_symbols:
            raise RiskError("Sembol izin listesinde değil")
        if side == "BUY" and self.max_trade_notional is not None and notional > self.max_trade_notional:
            raise RiskError("İşlem tutarı örnek risk limitini aşıyor")
        return quantity, price

    def check_after_buy(self, portfolio, symbol, price, *, now=None, market_prices=None, daily_loss=None):
        """Henüz kaydedilmemiş alışın komisyon dahil sonuçlarını denetler.

        Pozisyon değeri yalnızca işlem fiyatıyla ölçülür; başka semboller için
        fiyat tahmini yapılmaz. Bu iki sınır pozisyon azaltan satışa uygulanmaz.
        """
        if (self.min_cash_reserve is not None
                and portfolio.cash < self.min_cash_reserve):
            raise RiskError("Alış sonrası nakit örnek rezerv limitinin altında")
        if self.max_position_notional is not None:
            try:
                value = portfolio.positions[symbol].quantity * D(price)
                if not value.is_finite() or value > self.max_position_notional:
                    raise RiskError("Pozisyon değeri örnek risk limitini aşıyor")
            except DecimalException as exc:
                raise RiskError("Pozisyon değeri hesaplanamadı") from exc

        if self.max_daily_realized_loss is not None:
            if daily_loss is None or daily_loss >= self.max_daily_realized_loss:
                raise RiskError("Günlük gerçekleşen zarar limiti yeni alışı durdurdu")
        if self.max_total_position_notional is not None:
            total = Decimal(0)
            for held, position in portfolio.positions.items():
                if held == symbol:
                    value = D(price)
                else:
                    observation = (market_prices or {}).get(held)
                    from .market import PriceObservation
                    if not isinstance(observation, PriceObservation) or observation.symbol != held:
                        raise RiskError(f"{held} için toplam risk değerleme fiyatı yok")
                    self.check_price_time(observation.observed_at, now=now)
                    value = D(observation.price)
                    if not value.is_finite() or value <= 0:
                        raise RiskError("Geçersiz değerleme fiyatı")
                total += position.quantity * value
            if not total.is_finite() or total > self.max_total_position_notional:
                raise RiskError("Toplam pozisyon değeri risk limitini aşıyor")

    def check_price_time(self, observed_at, *, now):
        """İşlem zamanından bağımsız, karar anındaki saate göre kontrol eder."""
        if self.max_price_age is None:
            return
        for name, value in (("Fiyat gözlem zamanı", observed_at), ("Kontrol zamanı", now)):
            if not isinstance(value, datetime) or value.utcoffset() is None:
                raise RiskError(f"{name} saat dilimi içermeli")
        age = now.astimezone(timezone.utc) - observed_at.astimezone(timezone.utc)
        if age < timedelta(0):
            raise RiskError("Fiyat gözlem zamanı gelecekte olamaz")
        if age > self.max_price_age:
            raise RiskError("Fiyat izin verilen yaştan eski")
