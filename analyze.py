#!/usr/bin/env python3
"""Quant Autoresearch Agent — Portfolio Analysis CLI."""
import argparse
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.data.alpaca import AlpacaProvider
from src.data.db import Storage
from src.agents.portfolio_analyst import PortfolioAnalyst
from src.agents.risk_manager import RiskManager
from src.strategy.config import load_strategy
from src.models.types import PortfolioReport
from src.output.console import format_report
from src.output.json_writer import write_report

DEFAULT_STRATEGY = "strategies/v0.1.yaml"

def main():
    parser = argparse.ArgumentParser(description="Analyze stocks for buy/hold/sell")
    parser.add_argument("tickers", nargs="+", help="Stock tickers to analyze")
    parser.add_argument("--strategy", default=DEFAULT_STRATEGY, help="Strategy config path")
    parser.add_argument("--days", type=int, default=365, help="Days of history to fetch")
    args = parser.parse_args()

    load_dotenv()
    if not os.environ.get("ALPACA_API_KEY"):
        print("Error: Set ALPACA_API_KEY and ALPACA_SECRET in .env")
        sys.exit(1)

    # Load strategy
    print(f"Loading strategy: {args.strategy}")
    config = load_strategy(args.strategy)

    # Init data layer
    provider = AlpacaProvider()
    db = Storage()

    # Fetch bars
    tickers = [t.upper() for t in args.tickers]
    all_tickers = tickers + ["SPY"]  # benchmark
    end = datetime.now()
    start = end - timedelta(days=args.days)

    print(f"Fetching data for {len(tickers)} tickers + SPY...")
    all_bars_df = provider.get_bars(all_tickers, start, end)

    if all_bars_df.empty:
        print("No data returned. Check tickers and API keys.")
        sys.exit(1)

    # Organize bars by ticker
    bars = {}
    for ticker in all_tickers:
        mask = all_bars_df["symbol"] == ticker
        if mask.any():
            bars[ticker] = all_bars_df[mask].sort_values("timestamp").reset_index(drop=True)

    # Cache bars
    db.store_bars(all_bars_df)

    # Analyze
    print("Scoring...")
    analyst = PortfolioAnalyst(config)
    recommendations = analyst.analyze(tickers, bars)

    if not recommendations:
        print("No recommendations generated. Check ticker data.")
        db.close()
        return

    # Risk review
    risk_mgr = RiskManager()
    warnings = risk_mgr.review(recommendations, thresholds=config.thresholds)

    # Build report
    sorted_recs = sorted(recommendations, key=lambda r: r.composite_score, reverse=True)
    report = PortfolioReport(
        date=datetime.now(),
        strategy_version=config.version,
        recommendations=sorted_recs,
        warnings=warnings,
        strongest=sorted_recs[0].ticker if sorted_recs else "",
        weakest=sorted_recs[-1].ticker if sorted_recs else "",
    )

    # Output
    print(format_report(report))
    filepath = write_report(report)
    print(f"\nSaved to {filepath}")

    # Persist scores
    run_date = datetime.now()
    for rec in recommendations:
        db.store_recommendation(run_date, {
            "ticker": rec.ticker, "action": rec.action,
            "confidence": rec.confidence, "composite_score": rec.composite_score,
            "signal_scores": rec.signal_scores, "rationale": rec.rationale,
            "invalidation": rec.invalidation, "risk_params": rec.risk_params,
        })

    db.close()
    print("Done.")

if __name__ == "__main__":
    main()
