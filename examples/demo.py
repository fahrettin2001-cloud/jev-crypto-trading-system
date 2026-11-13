"""Örnek fiyatlarla basit bir sanal işlem senaryosu.

Çalıştırma: python -m examples.demo
"""

from decimal import Decimal

from jev import Portfolio, load_prices


def main() -> None:
    p = Portfolio(cash=Decimal("10000"))
    history = load_prices()

    first_ts, first = history[0]
    p.buy("BTCUSDT", Decimal("0.05"), first["BTCUSDT"], timestamp=first_ts)
    p.buy("ETHUSDT", Decimal("1"), first["ETHUSDT"], timestamp=first_ts)

    mid_ts, mid = history[len(history) // 2]
    p.sell("ETHUSDT", Decimal("0.5"), mid["ETHUSDT"], timestamp=mid_ts)

    last_ts, last = history[-1]
    print(f"Son fiyat zamanı : {last_ts:%Y-%m-%d}")
    print(f"Nakit            : {p.cash:.2f} {p.quote}")
    print(f"Pozisyon değeri  : {p.market_value(last):.2f}")
    print(f"Toplam varlık    : {p.equity(last):.2f}")
    print(f"Gerçekleşen K/Z  : {p.realized_pnl:.2f}")
    print(f"Gerçekleşmemiş   : {p.unrealized_pnl(last):.2f}")
    print(f"Ödenen komisyon  : {p.total_fees:.2f}")


if __name__ == "__main__":
    main()
