#!/usr/bin/env python3
"""Quant Autoresearch Agent -- Backtest CLI."""
import argparse
import os
import sys
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path

from src.data.alpaca import AlpacaProvider
from src.data.db import Storage
from src.strategy.config import load_strategy
from src.research.backtester import Backtester

DEFAULT_STRATEGY = "strategies/v0.1.yaml"

def main():
    parser = argparse.ArgumentParser(description="Backtest a strategy on historical data")
    parser.add_argument("tickers", nargs="+", help="Stock tickers to backtest")
    parser.add_argument("--strategy", default=DEFAULT_STRATEGY, help="Strategy config path")
    parser.add_argument("--days", type=int, default=730, help="Days of history (default 2 years)")
    parser.add_argument("--output", default="output", help="Output directory")
    args = parser.parse_args()

    load_dotenv()
    if not os.environ.get("ALPACA_API_KEY"):
        print("Error: Set ALPACA_API_KEY and ALPACA_SECRET in .env")
        sys.exit(1)

    config = load_strategy(args.strategy)
    provider = AlpacaProvider()

    tickers = [t.upper() for t in args.tickers]
    all_tickers = tickers + ["SPY"]
    end = datetime.now()
    start = end - timedelta(days=args.days)

    print(f"Fetching {args.days} days of data for {len(tickers)} tickers + SPY...")
    all_bars_df = provider.get_bars(all_tickers, start, end)

    if all_bars_df.empty:
        print("No data returned.")
        sys.exit(1)

    bars = {}
    for ticker in all_tickers:
        mask = all_bars_df["symbol"] == ticker
        if mask.any():
            bars[ticker] = all_bars_df[mask].sort_values("timestamp").reset_index(drop=True)

    print(f"Running backtest (strategy {config.version})...")
    bt = Backtester(config)
    result = bt.run(tickers, bars)

    print(f"\n{'='*60}")
    print(f"  Backtest Results -- strategy {config.version}")
    print(f"  {len(result.window_results)} walk-forward windows")
    print(f"{'='*60}\n")

    m = result.aggregate_metrics
    print(f"  Sharpe:       {m.get('sharpe', 0):.3f}")
    print(f"  CAGR:         {m.get('cagr', 0):.2%}")
    print(f"  Max Drawdown: {m.get('max_drawdown', 0):.2%}")
    print(f"  Hit Rate:     {m.get('hit_rate', 0):.2%}")
    print(f"  Turnover:     {m.get('monthly_turnover', 0):.2%}/mo")
    print(f"  Total Return: {m.get('total_return', 0):.2%}")

    print(f"\n  Per-Window Sharpe:")
    for w in result.window_results:
        status = "+" if w.metrics.get("sharpe", 0) > 0 else "-"
        print(f"    [{status}] Window {w.window_id}: "
              f"Sharpe {w.metrics.get('sharpe', 0):.3f}, "
              f"Return {w.metrics.get('total_return', 0):.2%} "
              f"({w.test_start} -> {w.test_end})")

    # Save results
    out_path = Path(args.output)
    out_path.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    filepath = out_path / f"backtest-{config.version}-{today}.json"
    filepath.write_text(json.dumps({
        "strategy_version": result.strategy_version,
        "aggregate_metrics": result.aggregate_metrics,
        "windows": [
            {"window_id": w.window_id, "test_start": w.test_start,
             "test_end": w.test_end, "metrics": w.metrics, "positions": w.positions}
            for w in result.window_results
        ],
        "config": result.config_snapshot,
    }, indent=2, default=str))
    print(f"\nSaved to {filepath}")

if __name__ == "__main__":
    main()
