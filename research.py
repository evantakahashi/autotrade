#!/usr/bin/env python3
"""Quant Autoresearch Agent — Research Loop CLI."""
import argparse
import logging
import os
import signal
import sys
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from dotenv import load_dotenv

from src.data.alpaca import AlpacaProvider
from src.research.loop import ResearchLoop


def setup_logging(log_dir: str = "logs"):
    """Configure logging to console + rotating file."""
    Path(log_dir).mkdir(exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    # File handler (10MB, keep 5 backups)
    file_handler = RotatingFileHandler(
        f"{log_dir}/research.log", maxBytes=10_000_000, backupCount=5
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)


def main():
    parser = argparse.ArgumentParser(description="Run the autoresearch loop")
    parser.add_argument("tickers", nargs="+", help="Tickers to research")
    parser.add_argument("--days", type=int, default=730, help="Days of history")
    parser.add_argument("--max-iterations", type=int, default=None, help="Max iterations (default: unlimited)")
    parser.add_argument("--cooldown", type=int, default=3600, help="Seconds between iterations")
    parser.add_argument("--max-rejections", type=int, default=10, help="Stop after N consecutive rejections")
    parser.add_argument("--log-dir", default="logs", help="Log directory")
    args = parser.parse_args()

    setup_logging(args.log_dir)
    logger = logging.getLogger("research")

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

    logger.info(f"Fetching {args.days} days of data for {len(tickers)} tickers + SPY...")
    all_bars_df = provider.get_bars(all_tickers, start, end)
    if all_bars_df.empty:
        logger.error("No data returned.")
        sys.exit(1)

    bars = {}
    for ticker in all_tickers:
        mask = all_bars_df["symbol"] == ticker
        if mask.any():
            bars[ticker] = all_bars_df[mask].sort_values("timestamp").reset_index(drop=True)

    logger.info(f"Starting research loop (cooldown={args.cooldown}s, max_rejections={args.max_rejections})...")
    loop = ResearchLoop(
        tickers=tickers, bars=bars,
        cooldown_seconds=args.cooldown,
        max_consecutive_rejections=args.max_rejections,
    )

    # Graceful shutdown handler
    def handle_signal(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name} — requesting graceful shutdown...")
        loop.shutdown_requested = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    results = loop.run(max_iterations=args.max_iterations)

    logger.info(f"Research loop complete — {len(results)} iterations")
    print(f"\n{'='*60}")
    print(f"  Research Loop Complete — {len(results)} iterations")
    print(f"{'='*60}")
    for r in results:
        phase = f" [{r.get('phase', 'backtest')}]" if r.get("phase") else ""
        status = "+" if r["decision"] == "promoted" else "~" if r["decision"] == "paper_testing" else "-"
        print(f"  {status} {r.get('experiment_id', '?')}: {r['decision']}{phase} — {r.get('hypothesis', '')[:60]}")


if __name__ == "__main__":
    main()
