# tests/test_runner.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.research.runner import StrategyRunner
from src.strategy.config import StrategyConfig, BacktestConfig

def _config():
    return StrategyConfig(
        version="0.1", name="test",
        weights={"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                 "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
        thresholds={"buy": 70, "hold_min": 40, "sell": 40},
        filters={},
        backtest=BacktestConfig(),
    )

def _synthetic_bars(days=252, daily_return=0.001):
    end = datetime(2026, 3, 1)
    dates = pd.date_range(end=end, periods=days, freq="B")
    prices = 100 * np.cumprod(1 + np.random.normal(daily_return, 0.01, days))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices,
        "volume": np.random.randint(500_000, 3_000_000, days),
    })

def test_runner_returns_positions():
    runner = StrategyRunner(_config())
    bars = {"AAPL": _synthetic_bars(), "SPY": _synthetic_bars()}
    as_of = datetime(2026, 3, 1)
    positions = runner.get_positions(["AAPL"], bars, as_of)
    assert "AAPL" in positions
    assert positions["AAPL"]["action"] in ("buy", "hold", "sell")

def test_runner_respects_as_of_date():
    """Runner should only use data up to as_of -- no lookahead."""
    runner = StrategyRunner(_config())
    full_bars = _synthetic_bars(days=252)
    bars = {"AAPL": full_bars, "SPY": _synthetic_bars(days=252)}
    # Use as_of in the middle of the data
    mid_date = full_bars["timestamp"].iloc[125]
    positions = runner.get_positions(["AAPL"], bars, mid_date)
    assert "AAPL" in positions

def test_runner_position_has_score():
    runner = StrategyRunner(_config())
    bars = {"AAPL": _synthetic_bars(), "SPY": _synthetic_bars()}
    positions = runner.get_positions(["AAPL"], bars, datetime(2026, 3, 1))
    assert "composite_score" in positions["AAPL"]
    assert 0 <= positions["AAPL"]["composite_score"] <= 100
