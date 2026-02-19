# src/research/metrics.py
import numpy as np
import pandas as pd

def compute_metrics(
    returns: pd.Series,
    transaction_cost_bps: float = 0,
    positions_changed: int = 0,
    total_positions: int = 1,
    months: float = 0,
) -> dict:
    """Compute backtest metrics from a daily returns series."""
    if len(returns) == 0:
        return _empty_metrics()

    # Apply transaction costs
    if transaction_cost_bps > 0 and positions_changed > 0:
        total_cost = positions_changed * (transaction_cost_bps / 10000)
        # Spread cost evenly across the period
        daily_cost = total_cost / max(len(returns), 1)
        returns = returns - daily_cost

    # Cumulative returns -> equity curve
    equity = (1 + returns).cumprod()
    total_return = float(equity.iloc[-1] - 1) if len(equity) > 0 else 0.0

    # Sharpe (annualized, assuming 0 risk-free rate)
    mean_r = returns.mean()
    std_r = returns.std()
    sharpe = float(mean_r / std_r * np.sqrt(252)) if std_r > 0 else 0.0

    # CAGR
    n_days = len(returns)
    if n_days > 0 and equity.iloc[-1] > 0:
        cagr = float(equity.iloc[-1] ** (252 / n_days) - 1)
    else:
        cagr = 0.0

    # Max drawdown
    peak = equity.cummax()
    drawdown = (equity - peak) / peak
    max_drawdown = float(abs(drawdown.min()))

    # Hit rate
    n_positive = int((returns > 0).sum())
    hit_rate = n_positive / len(returns) if len(returns) > 0 else 0.0

    # Win/loss ratio
    winners = returns[returns > 0]
    losers = returns[returns < 0]
    avg_win = float(winners.mean()) if len(winners) > 0 else 0.0
    avg_loss = float(abs(losers.mean())) if len(losers) > 0 else 1.0
    win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float("inf")

    # Turnover
    if months > 0 and total_positions > 0:
        monthly_turnover = (positions_changed / total_positions) / months
    else:
        monthly_turnover = 0.0

    return {
        "sharpe": round(sharpe, 3),
        "cagr": round(cagr, 4),
        "max_drawdown": round(max_drawdown, 4),
        "hit_rate": round(hit_rate, 4),
        "win_loss_ratio": round(win_loss_ratio, 3),
        "total_return": round(total_return, 4),
        "monthly_turnover": round(monthly_turnover, 4),
        "n_days": n_days,
    }

def _empty_metrics() -> dict:
    return {
        "sharpe": 0.0, "cagr": 0.0, "max_drawdown": 0.0,
        "hit_rate": 0.0, "win_loss_ratio": 0.0, "total_return": 0.0,
        "monthly_turnover": 0.0, "n_days": 0,
    }
