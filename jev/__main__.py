"""Çevrimdışı ve kalıcı sanal portföy komutları."""
import argparse
import json
import sqlite3

from . import FeeSchedule, Portfolio, TradeError


def main():
    parser = argparse.ArgumentParser(description="Çevrimdışı sanal portföy")
    parser.add_argument("--db", default="portfolio.sqlite3")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("cash")
    init.add_argument("--quote", default="USDT")
    init.add_argument("--maker-rate", default="0.001")
    init.add_argument("--taker-rate", default="0.001")
    for side in ("buy", "sell"):
        command = commands.add_parser(side)
        command.add_argument("symbol")
        command.add_argument("quantity")
        command.add_argument("price")
        command.add_argument("--maker", action="store_true")
    commands.add_parser("status")
    commands.add_parser("history")
    args = parser.parse_args()
    try:
        portfolio = (Portfolio.create(args.db, args.cash, FeeSchedule(args.maker_rate, args.taker_rate), args.quote)
                     if args.command == "init" else Portfolio.open(args.db))
        with portfolio:
            if args.command in ("buy", "sell"):
                getattr(portfolio, args.command)(args.symbol, args.quantity, args.price, taker=not args.maker)
            elif args.command == "status":
                print(json.dumps({"cash": str(portfolio.cash), "quote": portfolio.quote, "positions": {s: {"quantity": str(p.quantity), "avg_cost": str(p.avg_cost)} for s, p in portfolio.positions.items()}}, indent=2))
            elif args.command == "history":
                print(json.dumps([{"timestamp": t.timestamp.isoformat(), "symbol": t.symbol, "side": t.side, "quantity": str(t.quantity), "price": str(t.price), "fee": str(t.fee), "realized_pnl": str(t.realized_pnl)} for t in portfolio.trades], indent=2))
    except (ValueError, sqlite3.Error) as error:
        parser.exit(1, f"Hata: {error}\n")


if __name__ == "__main__":
    main()
