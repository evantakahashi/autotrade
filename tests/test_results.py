# tests/test_results.py
from src.research.results import BacktestResult, WindowResult

def test_window_result_creation():
    wr = WindowResult(
        window_id=0,
        train_start="2025-01-01", train_end="2025-06-30",
        test_start="2025-09-01", test_end="2025-09-30",
        metrics={"sharpe": 1.2, "cagr": 0.15, "max_drawdown": 0.08},
        positions={"AAPL": "buy", "MSFT": "hold"},
    )
    assert wr.metrics["sharpe"] == 1.2

def test_backtest_result_creation():
    wr = WindowResult(0, "2025-01-01", "2025-06-30", "2025-09-01", "2025-09-30",
                      {"sharpe": 1.2}, {})
    result = BacktestResult(
        strategy_version="0.1",
        window_results=[wr],
        aggregate_metrics={"sharpe": 1.2},
        config_snapshot={"weights": {"trend": 0.35}},
    )
    assert len(result.window_results) == 1
    assert result.aggregate_metrics["sharpe"] == 1.2

def test_backtest_result_win_rate():
    windows = [
        WindowResult(0, "", "", "", "", {"sharpe": 1.5}, {}),
        WindowResult(1, "", "", "", "", {"sharpe": 0.8}, {}),
        WindowResult(2, "", "", "", "", {"sharpe": 1.1}, {}),
    ]
    result = BacktestResult("0.1", windows, {}, {})
    # Helper: how many windows had sharpe > 1.0
    assert result.windows_passing(lambda m: m["sharpe"] > 1.0) == 2
