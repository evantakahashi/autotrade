# tests/test_db.py
import pandas as pd
from datetime import datetime
from src.data.db import Storage

def test_store_and_retrieve_bars(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    bars = pd.DataFrame({
        "symbol": ["AAPL", "AAPL"],
        "timestamp": [datetime(2026, 3, 1), datetime(2026, 3, 2)],
        "open": [150.0, 151.0],
        "high": [155.0, 156.0],
        "low": [149.0, 150.0],
        "close": [154.0, 155.0],
        "volume": [1000000, 1100000],
    })
    db.store_bars(bars)
    result = db.get_bars(["AAPL"], datetime(2026, 3, 1), datetime(2026, 3, 3))
    assert len(result) == 2

def test_store_and_retrieve_scores(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    db.store_score(
        run_date=datetime(2026, 3, 10), ticker="AAPL", signal="trend",
        score=85.0, confidence=0.9, components={"momentum_3m": 90}
    )
    scores = db.get_scores(datetime(2026, 3, 10))
    assert len(scores) == 1
    assert scores[0]["ticker"] == "AAPL"

def test_get_bars_multiple_tickers(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    bars = pd.DataFrame({
        "symbol": ["AAPL", "MSFT"],
        "timestamp": [datetime(2026, 3, 1), datetime(2026, 3, 1)],
        "open": [150.0, 300.0],
        "high": [155.0, 305.0],
        "low": [149.0, 298.0],
        "close": [154.0, 303.0],
        "volume": [1000000, 800000],
    })
    db.store_bars(bars)
    result = db.get_bars(["AAPL", "MSFT"], datetime(2026, 3, 1), datetime(2026, 3, 2))
    assert len(result) == 2

def test_bars_deduplication(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    bars = pd.DataFrame({
        "symbol": ["AAPL"],
        "timestamp": [datetime(2026, 3, 1)],
        "open": [150.0], "high": [155.0], "low": [149.0], "close": [154.0], "volume": [1000000],
    })
    db.store_bars(bars)
    db.store_bars(bars)  # insert same data again
    result = db.get_bars(["AAPL"], datetime(2026, 3, 1), datetime(2026, 3, 2))
    assert len(result) == 1
