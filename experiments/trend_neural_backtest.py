"""Offline paper comparison; decision close approximates next daily open."""
import argparse
import hashlib
import json
from pathlib import Path

from experiments.market_neural import fit_neural, transform
from experiments.team_neural import build_examples, load_daily
from jev.strategy import TrendRules

COST = 0.0015  # per traded notional, including commission and assumed slippage
SLEEVE = 0.30
REBALANCE = 0.10
THRESHOLD = 0.50  # fixed before evaluating; no tuning on either period


def features(prices, i):
    close = prices[i].close
    sma = sum(p.close for p in prices[i - 49:i + 1]) / 50
    return (float((close / prices[i - 30].close - 1) * 100),
            float((close / sma - 1) * 100))


def precompute(prices):
    training = build_examples(prices, "team")["train"]
    network, means, scales = fit_neural(training)
    rules = TrendRules()
    result = []
    for i, price in enumerate(prices):
        trend = float(rules.update(price.close))
        probability = (network.predict(*transform(features(prices, i), means, scales))
                       if i >= 49 else 0.5)
        result.append((trend, probability))
    return result


def simulate(prices, signals, start, end, filtered, cost=COST):
    """Rebalance at prior close proxy and mark at current close, long/cash only."""
    symbols = sorted(prices)
    if len(symbols) != 2 or set(signals) != set(symbols):
        raise ValueError("Exactly two aligned symbols and signals are required")
    dates = [p.time for p in prices[symbols[0]]]
    if any([p.time for p in prices[s]] != dates or len(signals[s]) != len(dates) for s in symbols):
        raise ValueError("Dates and signals must match")
    if not 0 <= cost < 1:
        raise ValueError("Invalid transaction cost")
    selected = [i for i, day in enumerate(dates) if start <= day.date().isoformat() <= end]
    if not selected or selected[0] == 0:
        raise ValueError("A prior decision and evaluation days are required")
    cash, holdings, fees, trades, peak, worst, exposure = 500.0, {s: 0.0 for s in symbols}, 0.0, 0, 500.0, 0.0, []
    for i in selected:
        prior = {s: float(prices[s][i - 1].close) for s in symbols}
        equity = cash + sum(holdings[s] * prior[s] for s in symbols)
        targets = {}
        for s in symbols:
            trend, p = signals[s][i - 1]
            targets[s] = equity * SLEEVE * trend * (not filtered or p >= THRESHOLD)
        # Sell first, then buy: both variants use exactly the same accounting.
        for s in symbols:
            held_value = holdings[s] * prior[s]
            gap = targets[s] - held_value
            if gap < 0 and (targets[s] == 0 or abs(gap) >= equity * SLEEVE * REBALANCE):
                value = min(-gap, held_value)
                holdings[s] -= value / prior[s]
                cash += value * (1 - cost)
                fees += value * cost
                trades += 1
        for s in symbols:
            gap = targets[s] - holdings[s] * prior[s]
            if gap > 0 and gap >= equity * SLEEVE * REBALANCE:
                value = min(gap, cash / (1 + cost))
                if value > 0:
                    holdings[s] += value / prior[s]
                    cash -= value * (1 + cost)
                    fees += value * cost
                    trades += 1
        invested = sum(holdings[s] * float(prices[s][i].close) for s in symbols)
        total = cash + invested
        peak = max(peak, total)
        worst = min(worst, total / peak - 1)
        exposure.append(invested / total)
    return {"initial": 500.0, "final": total, "return": total / 500 - 1,
            "max_drawdown": worst, "cost_paid": fees, "trades": trades,
            "mean_exposure": sum(exposure) / len(exposure), "days": len(selected)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--btc", type=Path, required=True)
    parser.add_argument("--eth", type=Path, required=True)
    args = parser.parse_args()
    paths = {"BTC": args.btc, "ETH": args.eth}
    prices = {s: load_daily(path) for s, path in paths.items()}
    signals = {s: precompute(rows) for s, rows in prices.items()}
    reports = {}
    for period, start, end in (("validation", "2023-01-01", "2023-12-31"),
                               ("previously_seen_test", "2024-01-01", "2026-10-31")):
        reports[period] = {"trend": simulate(prices, signals, start, end, False),
                           "trend_neural": simulate(prices, signals, start, end, True)}
    print(json.dumps({"sha256": {s: hashlib.sha256(p.read_bytes()).hexdigest() for s, p in paths.items()},
                      "threshold": THRESHOLD, "cost_per_trade": COST, "periods": reports}, indent=2))


if __name__ == "__main__":
    main()
