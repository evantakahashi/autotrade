# tests/test_trend.py
import pandas as pd
import numpy as np
from datetime import datetime
from src.agents.signals.trend import TrendSignal

def _make_uptrend(days=252):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    prices = 100 * np.cumprod(1 + np.random.normal(0.001, 0.008, days))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices,
        "volume": np.random.randint(500_000, 2_000_000, days),
    })

def _make_downtrend(days=252):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    prices = 100 * np.cumprod(1 + np.random.normal(-0.001, 0.008, days))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 1.01, "high": prices * 1.02,
        "low": prices * 0.99, "close": prices,
        "volume": np.random.randint(500_000, 2_000_000, days),
    })

def test_uptrend_scores_higher():
    signal = TrendSignal()
    up = signal.score("UP", _make_uptrend())
    down = signal.score("DOWN", _make_downtrend())
    assert up.score > down.score

def test_score_in_range():
    signal = TrendSignal()
    result = signal.score("TEST", _make_uptrend())
    assert 0 <= result.score <= 100
    assert result.signal == "trend"

def test_components_present():
    signal = TrendSignal()
    result = signal.score("TEST", _make_uptrend())
    assert "momentum" in result.components
    assert "sma_structure" in result.components
    assert "vol_contraction" in result.components
    assert "volume_confirm" in result.components

def test_explain_returns_string():
    signal = TrendSignal()
    result = signal.score("TEST", _make_uptrend())
    explanation = signal.explain(result)
    assert isinstance(explanation, str)
    assert "TEST" in explanation
