"""Mevcut SQLite ve risk katmanı üzerinden çevrimdışı sanal işlem komutları."""
import argparse
from dataclasses import asdict
from datetime import datetime, timedelta
from decimal import Decimal, DecimalException
import json
from pathlib import Path
import sqlite3

from . import FeeSchedule, RiskLimits, SQLitePortfolio
from .policy import parse_policy, policy_dict


def read_risk(path):
    """Her işlemde açıkça seçilmiş politika; bilinmeyen ayarlar reddedilir."""
    return parse_policy(json.loads(Path(path).read_text(encoding="utf-8"), parse_float=Decimal))


def output(value):
    print(json.dumps(value, ensure_ascii=False, indent=2,
                     default=lambda v: v.isoformat() if isinstance(v, datetime) else str(v)))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Çevrimdışı sanal portföy; gerçek emir göndermez")
    parser.add_argument("--db", type=Path, required=True, help="SQLite hesap dosyası")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Yeni hesap oluştur; mevcut dosyayı değiştirme")
    init.add_argument("cash")
    init.add_argument("--risk", type=Path, help="Hesaba kalıcı kaydedilecek risk JSON dosyası")
    init.add_argument("--quote", default="USDT")
    init.add_argument("--maker-rate", default="0.001")
    init.add_argument("--taker-rate", default="0.001")
    for side in ("buy", "sell"):
        command = commands.add_parser(side)
        command.add_argument("symbol")
        command.add_argument("quantity")
        command.add_argument("price", help="Elle verilen çevrimdışı fiyat")
        command.add_argument("--maker", action="store_true")
        command.add_argument("--risk", type=Path, help="JSON risk politikası")
        command.add_argument("--price-observed-at", help="Saat dilimli ISO 8601 fiyat gözlem zamanı")
    commands.add_parser("status", help="Bakiye, pozisyonlar, komisyonlar ve gerçekleşen K/Z")
    commands.add_parser("history", help="İşlem geçmişi")
    commands.add_parser("risk-show", help="Hesabın kayıtlı risk politikası ve sürümü")
    risk_set = commands.add_parser("risk-set", help="Risk politikasını açıkça değiştir")
    risk_set.add_argument("--risk", required=True, type=Path)
    risk_set.add_argument("--expected-version", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            cash = Decimal(args.cash)
            if not cash.is_finite() or cash < 0 or not args.quote.strip():
                raise ValueError("Başlangıç nakdi sonlu/negatif olmayan, para birimi dolu olmalı")
            fees = FeeSchedule(args.maker_rate, args.taker_rate)
            initial_risk = read_risk(args.risk) if args.risk is not None else None
            # Özel oluşturma mevcut bir dosyanın yanlışlıkla sıfırlanmasını önler.
            with args.db.open("xb"):
                pass
            try:
                with SQLitePortfolio(args.db, initial_cash=cash, fees=fees, quote=args.quote, risk=initial_risk) as account:
                    initial = account.portfolio.cash
            except BaseException:
                args.db.unlink()
                raise
            output({"cash": initial, "quote": args.quote})
            return
        risk = (read_risk(args.risk) if args.command in ("buy", "sell") and args.risk is not None else None)
        observed_at = (datetime.fromisoformat(args.price_observed_at)
                       if getattr(args, "price_observed_at", None) else None)
        with SQLitePortfolio.open(args.db, risk=risk) as account:
            if args.command in ("buy", "sell"):
                trade = getattr(account, args.command)(args.symbol, args.quantity, args.price,
                    taker=not args.maker, price_observed_at=observed_at)
                output(asdict(trade))
            elif args.command == "risk-set":
                version = account.set_risk(read_risk(args.risk), expected_version=args.expected_version)
                output({"risk_version": version})
            elif args.command == "risk-show":
                version, policy = account.policy_status()
                output({"risk_version": version, "policy": policy_dict(policy)})
            else:
                p = account.portfolio
                if args.command == "history":
                    output([asdict(t) for t in p.trades])
                else:
                    output({"cash": p.cash, "initial_cash": p.initial_cash, "quote": p.quote,
                            "positions": {s: asdict(pos) for s, pos in p.positions.items()},
                            "total_fees": p.total_fees, "realized_pnl": p.realized_pnl})
    except (OSError, ValueError, TypeError, DecimalException, OverflowError, sqlite3.Error) as exc:
        parser.exit(1, f"Hata: {exc}\n")


if __name__ == "__main__":
    main()
