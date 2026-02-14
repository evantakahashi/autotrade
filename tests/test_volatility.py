# tests/test_volatility.py
import pandas as pd
import numpy as np
from datetime import datetime
from src.agents.signals.volatility import VolatilitySignal

def _make_stable(days=252):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    prices = 100 + np.cumsum(np.random.normal(0.05, 0.3, days))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 0.999, "high": prices * 1.005,
        "low": prices * 0.995, "close": prices, "volume": [2_000_000] * days,
    })

def _make_volatile(days=252):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    prices = 100 + np.cumsum(np.random.normal(0, 3, days))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 0.97, "high": prices * 1.05,
        "low": prices * 0.95, "close": prices, "volume": [2_000_000] * days,
    })

def test_stable_scores_higher():
    signal = VolatilitySignal()
    stable = signal.score("SAFE", _make_stable())
    wild = signal.score("WILD", _make_volatile())
    assert stable.score > wild.score

def test_components_include_risk_params():
    signal = VolatilitySignal()
    result = signal.score("TEST", _make_stable())
    assert "annual_vol_pct" in result.components
    assert "max_drawdown_pct" in result.components
    assert "stop_loss" in result.components
    assert "max_position_pct" in result.components

def test_score_in_range():
    signal = VolatilitySignal()
    result = signal.score("TEST", _make_stable())
    assert 0 <= result.score <= 100
