# tests/test_liquidity.py
import pandas as pd
import numpy as np
from datetime import datetime
from src.agents.signals.liquidity import LiquiditySignal

def _make_bars(avg_volume=1_000_000, price=100.0, days=60):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    return pd.DataFrame({
        "timestamp": dates, "open": [price]*days, "high": [price*1.01]*days,
        "low": [price*0.99]*days, "close": [price]*days,
        "volume": np.random.randint(int(avg_volume*0.8), int(avg_volume*1.2), days),
    })

def test_high_volume_scores_higher():
    signal = LiquiditySignal()
    liquid = signal.score("LIQ", _make_bars(avg_volume=5_000_000, price=100))
    illiquid = signal.score("ILLIQ", _make_bars(avg_volume=50_000, price=5))
    assert liquid.score > illiquid.score

def test_score_in_range():
    signal = LiquiditySignal()
    result = signal.score("TEST", _make_bars())
    assert 0 <= result.score <= 100
    assert result.signal == "liquidity"
