import argparse
import json
import sqlite3

from .portfolio import Portfolio, TradeError


def main():
    parser = argparse.ArgumentParser(description="Çevrimdışı sanal portföy")
    parser.add_argument("--db", default="portfolio.sqlite3", help="SQLite dosyası")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("cash")
    init.add_argument("--quote", default="USDT")
    for side in ("buy", "sell"):
        trade = commands.add_parser(side)
        trade.add_argument("asset")
        trade.add_argument("quantity")
        trade.add_argument("price")
        trade.add_argument("--fee-rate", default="0")
    commands.add_parser("status")
    commands.add_parser("history")
    args = parser.parse_args()
    try:
        with Portfolio(args.db) as portfolio:
            if args.command == "init":
                portfolio.initialize(args.cash, args.quote)
            elif args.command in ("buy", "sell"):
                portfolio.trade(args.command, args.asset, args.quantity, args.price, args.fee_rate)
            elif args.command == "status":
                print(json.dumps({k: str(v) for k, v in portfolio.balances().items()}, ensure_ascii=False, indent=2))
            else:
                print(json.dumps(portfolio.history(), ensure_ascii=False, indent=2))
    except (TradeError, sqlite3.Error) as error:
        parser.exit(1, f"Hata: {error}\n")


if __name__ == "__main__":
    main()
