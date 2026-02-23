# src/research/auditor.py
from src.research.results import BacktestResult

def evaluate_gates(
    baseline: BacktestResult,
    experiment: BacktestResult,
    max_drawdown_ratio: float = 1.5,
    max_turnover_ratio: float = 2.0,
    min_window_win_rate: float = 0.75,
) -> dict:
    """Evaluate all validation gates. Returns verdict dict."""
    b_windows = baseline.window_results
    e_windows = experiment.window_results
    n = min(len(b_windows), len(e_windows))

    gates = []

    # Gate 1: Sharpe improvement on aggregate
    b_sharpe = baseline.aggregate_metrics.get("sharpe", 0)
    e_sharpe = experiment.aggregate_metrics.get("sharpe", 0)
    gates.append({
        "name": "sharpe",
        "passed": e_sharpe > b_sharpe,
        "detail": f"baseline={b_sharpe:.3f}, experiment={e_sharpe:.3f}",
    })

    # Gate 2: Walk-forward consistency
    windows_won = 0
    for i in range(n):
        if e_windows[i].metrics.get("sharpe", 0) > b_windows[i].metrics.get("sharpe", 0):
            windows_won += 1
    win_rate = windows_won / n if n > 0 else 0
    gates.append({
        "name": "walk_forward",
        "passed": win_rate >= min_window_win_rate,
        "detail": f"won {windows_won}/{n} windows ({win_rate:.0%}), need {min_window_win_rate:.0%}",
    })

    # Gate 3: Drawdown
    b_max_dd = max((w.metrics.get("max_drawdown", 0) for w in b_windows), default=0)
    e_max_dd = max((w.metrics.get("max_drawdown", 0) for w in e_windows), default=0)
    dd_ok = e_max_dd <= b_max_dd * max_drawdown_ratio if b_max_dd > 0 else True
    if b_max_dd > 0:
        dd_detail = (f"baseline_max={b_max_dd:.3f}, experiment_max={e_max_dd:.3f}, "
                     f"ratio={e_max_dd/b_max_dd:.2f}x")
    else:
        dd_detail = "no baseline drawdown"
    gates.append({
        "name": "drawdown",
        "passed": dd_ok,
        "detail": dd_detail,
    })

    # Gate 4: Turnover
    b_turnover = baseline.aggregate_metrics.get("monthly_turnover", 0)
    e_turnover = experiment.aggregate_metrics.get("monthly_turnover", 0)
    to_ok = e_turnover <= b_turnover * max_turnover_ratio if b_turnover > 0 else True
    gates.append({
        "name": "turnover",
        "passed": to_ok,
        "detail": f"baseline={b_turnover:.3f}, experiment={e_turnover:.3f}",
    })

    # Gate 5: Regime diversity
    up_wins = 0
    up_total = 0
    down_wins = 0
    down_total = 0
    for i in range(n):
        spy_ret = e_windows[i].metrics.get("spy_return")
        if spy_ret is None:
            # Can't classify regime — skip gate
            continue
        e_sharpe_w = e_windows[i].metrics.get("sharpe", 0)
        b_sharpe_w = b_windows[i].metrics.get("sharpe", 0)
        if spy_ret >= 0:
            up_total += 1
            if e_sharpe_w > b_sharpe_w:
                up_wins += 1
        else:
            down_total += 1
            if e_sharpe_w > b_sharpe_w:
                down_wins += 1

    if up_total > 0 and down_total > 0:
        regime_ok = up_wins > 0 and down_wins > 0
        gates.append({
            "name": "regime_diversity",
            "passed": regime_ok,
            "detail": f"up markets: won {up_wins}/{up_total}, down markets: won {down_wins}/{down_total}",
        })
    else:
        gates.append({
            "name": "regime_diversity",
            "passed": True,
            "detail": "insufficient regime data — gate skipped",
        })

    # Gate 6: Paper trading (stubbed — always passes in M3)
    gates.append({
        "name": "paper_trading",
        "passed": True,
        "detail": "stubbed — paper trading gate not enforced until M5",
    })

    overall = "pass" if all(g["passed"] for g in gates) else "fail"
    failed_gates = [g["name"] for g in gates if not g["passed"]]

    return {
        "overall": overall,
        "gates": gates,
        "failed_gates": failed_gates,
    }
