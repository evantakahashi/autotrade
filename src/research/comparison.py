# src/research/comparison.py
from src.research.results import BacktestResult

def compare_strategies(
    baseline: BacktestResult,
    experiment: BacktestResult,
    max_drawdown_ratio: float = 1.5,
) -> dict:
    """Compare two backtest results. Returns comparison dict."""
    b_windows = baseline.window_results
    e_windows = experiment.window_results
    n = min(len(b_windows), len(e_windows))

    if n == 0:
        return {"experiment_wins": False, "reason": "no windows to compare"}

    # Per-window comparison
    windows_won = 0
    for i in range(n):
        b_sharpe = b_windows[i].metrics.get("sharpe", 0)
        e_sharpe = e_windows[i].metrics.get("sharpe", 0)
        if e_sharpe > b_sharpe:
            windows_won += 1

    win_rate = windows_won / n

    # Aggregate comparison
    b_sharpe_agg = baseline.aggregate_metrics.get("sharpe", 0)
    e_sharpe_agg = experiment.aggregate_metrics.get("sharpe", 0)
    sharpe_improvement = e_sharpe_agg - b_sharpe_agg

    # Drawdown check
    b_max_dd = max((w.metrics.get("max_drawdown", 0) for w in b_windows), default=0)
    e_max_dd = max((w.metrics.get("max_drawdown", 0) for w in e_windows), default=0)
    drawdown_flag = e_max_dd > b_max_dd * max_drawdown_ratio if b_max_dd > 0 else False

    # Turnover check
    b_turnover = baseline.aggregate_metrics.get("monthly_turnover", 0)
    e_turnover = experiment.aggregate_metrics.get("monthly_turnover", 0)
    turnover_flag = e_turnover > b_turnover * 2 if b_turnover > 0 else False

    experiment_wins = (
        sharpe_improvement > 0 and
        win_rate >= 0.75 and
        not drawdown_flag
    )

    return {
        "experiment_wins": experiment_wins,
        "sharpe_improvement": round(sharpe_improvement, 4),
        "baseline_sharpe": round(b_sharpe_agg, 4),
        "experiment_sharpe": round(e_sharpe_agg, 4),
        "windows_won": windows_won,
        "windows_total": n,
        "win_rate": round(win_rate, 4),
        "drawdown_flag": drawdown_flag,
        "turnover_flag": turnover_flag,
        "baseline_max_dd": round(b_max_dd, 4),
        "experiment_max_dd": round(e_max_dd, 4),
    }
