# tests/test_backtest_integration.py
"""End-to-end: synthetic data -> backtester -> comparison."""
import numpy as np
import pandas as pd
from datetime import datetime
from src.strategy.config import StrategyConfig, BacktestConfig
from src.research.backtester import Backtester
from src.research.comparison import compare_strategies

def _config(weights_override=None):
    weights = {"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
               "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10}
    if weights_override:
        weights.update(weights_override)
    return StrategyConfig(
        version="0.1", name="test", weights=weights,
        thresholds={"buy": 70, "hold_min": 40, "sell": 40}, filters={},
        backtest=BacktestConfig(train_months=4, validation_months=1,
                                test_months=1, step_months=1,
                                transaction_cost_bps=10),
    )

def _universe(days=504):
    end = datetime(2026, 1, 1)
    dates = pd.date_range(end=end, periods=days, freq="B")
    bars = {}
    for t in ["AAPL", "MSFT", "GOOG", "SPY"]:
        np.random.seed(hash(t) % 2**31)
        dr = np.random.normal(0.0005, 0.012, days)
        prices = 100 * np.cumprod(1 + dr)
        bars[t] = pd.DataFrame({
            "timestamp": dates, "open": prices * 0.99, "high": prices * 1.01,
            "low": prices * 0.98, "close": prices,
            "volume": np.random.randint(500_000, 3_000_000, days),
        })
    return bars

def test_full_backtest_pipeline():
    config = _config()
    bars = _universe()
    bt = Backtester(config)
    result = bt.run(["AAPL", "MSFT", "GOOG"], bars)
    assert len(result.window_results) >= 3
    assert "sharpe" in result.aggregate_metrics
    assert "cagr" in result.aggregate_metrics
    assert "max_drawdown" in result.aggregate_metrics

def test_two_configs_comparison():
    bars = _universe()
    baseline = Backtester(_config()).run(["AAPL", "MSFT", "GOOG"], bars)
    # Modify weights slightly
    experiment = Backtester(
        _config(weights_override={"trend": 0.45, "fundamentals": 0.10})
    ).run(["AAPL", "MSFT", "GOOG"], bars)

    comparison = compare_strategies(baseline, experiment)
    assert "experiment_wins" in comparison
    assert "sharpe_improvement" in comparison
    assert isinstance(comparison["windows_won"], int)
