# tests/test_stubs.py
import pandas as pd
import numpy as np
from datetime import datetime
from src.agents.signals.fundamentals import FundamentalsSignal
from src.agents.signals.sentiment import SentimentSignal

def _make_bars(days=60):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    return pd.DataFrame({
        "timestamp": dates, "open": [100]*days, "high": [101]*days,
        "low": [99]*days, "close": [100]*days, "volume": [1_000_000]*days,
    })

def test_fundamentals_stub_returns_neutral():
    signal = FundamentalsSignal()
    result = signal.score("AAPL", _make_bars())
    assert result.score == 50.0
    assert result.confidence == 0.0

def test_sentiment_stub_returns_neutral():
    signal = SentimentSignal()
    result = signal.score("AAPL", _make_bars())
    assert result.score == 50.0
    assert result.confidence == 0.0

def test_fundamentals_explain():
    signal = FundamentalsSignal()
    result = signal.score("AAPL", _make_bars())
    assert "stubbed" in signal.explain(result).lower() or "not available" in signal.explain(result).lower()

def test_sentiment_explain():
    signal = SentimentSignal()
    result = signal.score("AAPL", _make_bars())
    assert "stubbed" in signal.explain(result).lower() or "not available" in signal.explain(result).lower()
