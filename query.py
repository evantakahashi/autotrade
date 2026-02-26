#!/usr/bin/env python3
"""Read-only query helper for Claude Code subagents."""
import argparse
import json
import sys
from src.data.db import Storage

DEFAULT_DB = "data/trading_agent.duckdb"


def cmd_experiments(db: Storage, args):
    rows = db.get_recent_experiments(limit=args.last)
    print(json.dumps(rows, indent=2, default=str))


def cmd_experiment(db: Storage, args):
    row = db.get_experiment(args.id)
    if row is None:
        print(f"Experiment '{args.id}' not found", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(row, indent=2, default=str))


def cmd_strategy(db: Storage, args):
    if args.current:
        row = db.get_latest_strategy_version()
        if row is None:
            print("No strategy versions found", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(row, indent=2, default=str))
    elif args.history:
        rows = db.get_strategy_versions()
        print(json.dumps(rows, indent=2, default=str))
    else:
        print("Specify --current or --history", file=sys.stderr)
        sys.exit(1)


def cmd_scores(db: Storage, args):
    rows = db.conn.execute(
        "SELECT * FROM scores WHERE ticker = ? ORDER BY run_date DESC LIMIT ?",
        [args.ticker, args.last]
    ).fetchdf().to_dict("records")
    print(json.dumps(rows, indent=2, default=str))


def main():
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--db", default=DEFAULT_DB, help="DB path")

    parser = argparse.ArgumentParser(description="Query trading agent DB (read-only)", parents=[parent])
    sub = parser.add_subparsers(dest="command")

    p_exps = sub.add_parser("experiments", help="List recent experiments", parents=[parent])
    p_exps.add_argument("--last", type=int, default=10)

    p_exp = sub.add_parser("experiment", help="Get experiment by ID", parents=[parent])
    p_exp.add_argument("--id", required=True)

    p_strat = sub.add_parser("strategy", help="Query strategy versions", parents=[parent])
    p_strat.add_argument("--current", action="store_true")
    p_strat.add_argument("--history", action="store_true")

    p_scores = sub.add_parser("scores", help="Query scores by ticker", parents=[parent])
    p_scores.add_argument("--ticker", required=True)
    p_scores.add_argument("--last", type=int, default=10)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    db = Storage(args.db)
    try:
        {"experiments": cmd_experiments, "experiment": cmd_experiment,
         "strategy": cmd_strategy, "scores": cmd_scores}[args.command](db, args)
    finally:
        db.close()


if __name__ == "__main__":
    main()
