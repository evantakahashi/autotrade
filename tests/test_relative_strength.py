# tests/test_relative_strength.py
import pandas as pd
import numpy as np
from datetime import datetime
from src.agents.signals.relative_strength import RelativeStrengthSignal

def _make_bars(daily_return=0.001, days=252):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    prices = 100 * np.cumprod(1 + np.random.normal(daily_return, 0.008, days))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices,
        "volume": np.random.randint(500_000, 2_000_000, days),
    })

def test_outperformer_scores_higher():
    signal = RelativeStrengthSignal()
    spy = _make_bars(daily_return=0.0005)
    strong = signal.score("STRONG", _make_bars(daily_return=0.002), benchmark_bars=spy)
    weak = signal.score("WEAK", _make_bars(daily_return=-0.001), benchmark_bars=spy)
    assert strong.score > weak.score

def test_score_in_range():
    signal = RelativeStrengthSignal()
    spy = _make_bars()
    result = signal.score("TEST", _make_bars(), benchmark_bars=spy)
    assert 0 <= result.score <= 100
    assert result.signal == "relative_strength"

def test_no_benchmark_returns_neutral():
    signal = RelativeStrengthSignal()
    result = signal.score("TEST", _make_bars(), benchmark_bars=None)
    assert result.score == 50.0
