# src/output/console.py
from src.models.types import PortfolioReport

SIGNAL_COLS = ["trend", "relative_strength", "volatility", "liquidity", "fundamentals", "sentiment"]

def format_report(report: PortfolioReport) -> str:
    lines = [
        f"\n{'='*70}",
        f"  Portfolio Analysis — {report.date.strftime('%Y-%m-%d')}  (strategy {report.strategy_version})",
        f"{'='*70}\n",
    ]

    # Summary
    if report.strongest:
        lines.append(f"  Strongest: {report.strongest}")
    if report.weakest:
        lines.append(f"  Weakest:   {report.weakest}")
    lines.append("")

    # Table header
    header = f" {'Ticker':<6} {'Action':<6} {'Score':>6} {'Conf':>5}"
    for col in SIGNAL_COLS:
        short = col[:5].title()
        header += f" {short:>6}"
    lines.append(header)
    lines.append("-" * len(header))

    # Rows
    for r in report.recommendations:
        action_str = r.action.upper()
        row = f" {r.ticker:<6} {action_str:<6} {r.composite_score:>6.1f} {r.confidence:>5.0%}"
        for col in SIGNAL_COLS:
            val = r.signal_scores.get(col, 0)
            row += f" {val:>6.1f}"
        lines.append(row)

    # Warnings
    if report.warnings:
        lines.append("")
        for w in report.warnings:
            lines.append(f"  ! {w}")

    # Per-stock details
    lines.append("")
    for r in report.recommendations:
        lines.append(f"-- {r.ticker} [{r.action.upper()}] --")
        if r.rationale:
            lines.append(f"  Rationale: {r.rationale}")
        if r.risk_params.get("stop_loss"):
            lines.append(f"  Risk: Stop ${r.risk_params['stop_loss']}, max {r.risk_params.get('max_position_pct', '?')}% portfolio")
        if r.invalidation:
            lines.append(f"  Invalidation: {r.invalidation}")
        lines.append("")

    return "\n".join(lines)
