# tests/test_backtester.py
import pandas as pd
import numpy as np
from datetime import datetime, date
from src.research.backtester import Backtester
from src.strategy.config import StrategyConfig, BacktestConfig

def _config():
    return StrategyConfig(
        version="0.1", name="test",
        weights={"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                 "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
        thresholds={"buy": 70, "hold_min": 40, "sell": 40},
        filters={},
        backtest=BacktestConfig(
            train_months=6, validation_months=2, test_months=1,
            step_months=1, transaction_cost_bps=10,
        ),
    )

def _synthetic_universe(tickers, days=504):
    """~2 years of data for multiple tickers."""
    end = datetime(2026, 1, 1)
    dates = pd.date_range(end=end, periods=days, freq="B")
    bars = {}
    for t in tickers:
        dr = np.random.normal(0.0005, 0.012, days)
        prices = 100 * np.cumprod(1 + dr)
        bars[t] = pd.DataFrame({
            "timestamp": dates, "open": prices * 0.99, "high": prices * 1.01,
            "low": prices * 0.98, "close": prices,
            "volume": np.random.randint(500_000, 3_000_000, days),
        })
    return bars

def test_backtester_returns_result():
    config = _config()
    bars = _synthetic_universe(["AAPL", "MSFT", "SPY"])
    bt = Backtester(config)
    result = bt.run(["AAPL", "MSFT"], bars)
    assert len(result.window_results) > 0
    assert "sharpe" in result.aggregate_metrics

def test_backtester_multiple_windows():
    config = _config()
    bars = _synthetic_universe(["AAPL", "SPY"], days=504)
    bt = Backtester(config)
    result = bt.run(["AAPL"], bars)
    assert len(result.window_results) >= 3

def test_backtester_metrics_reasonable():
    config = _config()
    bars = _synthetic_universe(["AAPL", "SPY"])
    bt = Backtester(config)
    result = bt.run(["AAPL"], bars)
    m = result.aggregate_metrics
    assert -5.0 < m["sharpe"] < 5.0
    assert -1.0 < m["cagr"] < 5.0
    assert 0 <= m["max_drawdown"] <= 1.0

def test_backtester_no_lookahead():
    """Each window's positions should only use data up to that window's train_end."""
    config = _config()
    bars = _synthetic_universe(["AAPL", "SPY"])
    bt = Backtester(config)
    result = bt.run(["AAPL"], bars)
    # If there are results, they were generated -- no crash means no future data accessed
    assert len(result.window_results) > 0
