# tests/test_comparison.py
from src.research.comparison import compare_strategies
from src.research.results import BacktestResult, WindowResult

def _result(sharpe_values, version="0.1"):
    windows = [
        WindowResult(i, "", "", "", "", {"sharpe": s, "cagr": s * 0.05,
                     "max_drawdown": 0.1, "hit_rate": 0.55, "monthly_turnover": 0.2},
                     {})
        for i, s in enumerate(sharpe_values)
    ]
    agg = {"sharpe": sum(sharpe_values) / len(sharpe_values)}
    return BacktestResult(version, windows, agg, {})

def test_better_strategy_wins():
    baseline = _result([0.8, 0.9, 1.0, 0.7])
    experiment = _result([1.2, 1.3, 1.1, 1.4], version="0.2")
    comparison = compare_strategies(baseline, experiment)
    assert comparison["experiment_wins"]
    assert comparison["sharpe_improvement"] > 0

def test_worse_strategy_loses():
    baseline = _result([1.2, 1.3, 1.1, 1.4])
    experiment = _result([0.5, 0.6, 0.4, 0.3], version="0.2")
    comparison = compare_strategies(baseline, experiment)
    assert not comparison["experiment_wins"]

def test_comparison_has_per_window_detail():
    baseline = _result([0.8, 0.9, 1.0, 0.7])
    experiment = _result([1.2, 0.7, 1.1, 0.9], version="0.2")
    comparison = compare_strategies(baseline, experiment)
    assert "windows_won" in comparison
    assert "windows_total" in comparison
    assert comparison["windows_total"] == 4

def test_comparison_drawdown_check():
    baseline = _result([1.0, 1.0, 1.0, 1.0])
    # Experiment has better sharpe but worse drawdown
    windows = [
        WindowResult(i, "", "", "", "",
                     {"sharpe": 1.5, "max_drawdown": 0.3, "cagr": 0.1,
                      "hit_rate": 0.5, "monthly_turnover": 0.2}, {})
        for i in range(4)
    ]
    experiment = BacktestResult("0.2", windows, {"sharpe": 1.5}, {})
    comparison = compare_strategies(baseline, experiment, max_drawdown_ratio=1.5)
    assert "drawdown_flag" in comparison
