#!/usr/bin/env python3
"""Quant Autoresearch Agent — Research Loop CLI."""
import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.data.alpaca import AlpacaProvider
from src.research.loop import ResearchLoop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def main():
    parser = argparse.ArgumentParser(description="Run the autoresearch loop")
    parser.add_argument("tickers", nargs="+", help="Tickers to research")
    parser.add_argument("--days", type=int, default=730, help="Days of history")
    parser.add_argument("--max-iterations", type=int, default=None, help="Max iterations (default: unlimited)")
    parser.add_argument("--cooldown", type=int, default=3600, help="Seconds between iterations")
    parser.add_argument("--max-rejections", type=int, default=10, help="Stop after N consecutive rejections")
    args = parser.parse_args()

    load_dotenv()
    for key in ["ALPACA_API_KEY", "ALPACA_SECRET", "ANTHROPIC_API_KEY"]:
        if not os.environ.get(key):
            print(f"Error: Set {key} in .env")
            sys.exit(1)

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

    print(f"Starting research loop (cooldown={args.cooldown}s, max_rejections={args.max_rejections})...")
    loop = ResearchLoop(
        tickers=tickers, bars=bars,
        cooldown_seconds=args.cooldown,
        max_consecutive_rejections=args.max_rejections,
    )
    results = loop.run(max_iterations=args.max_iterations)

    print(f"\n{'='*60}")
    print(f"  Research Loop Complete — {len(results)} iterations")
    print(f"{'='*60}")
    for r in results:
        status = "+" if r["decision"] == "promoted" else "-"
        print(f"  {status} {r.get('experiment_id', '?')}: {r['decision']} — {r.get('hypothesis', '')[:60]}")

if __name__ == "__main__":
    main()
