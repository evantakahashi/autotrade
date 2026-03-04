# tests/test_graceful_shutdown.py
import pytest
import signal
import pandas as pd
from unittest.mock import MagicMock, patch
from src.research.loop import ResearchLoop
from src.data.db import Storage


def test_shutdown_flag_stops_loop(tmp_path):
    """Setting shutdown_requested stops the loop cleanly."""
    db_path = str(tmp_path / "test.duckdb")
    strategies_dir = str(tmp_path / "strategies")
    import os, shutil
    os.makedirs(strategies_dir, exist_ok=True)
    shutil.copy("strategies/v0.1.yaml", f"{strategies_dir}/v0.1.yaml")

    dates = pd.date_range("2023-01-15", periods=24, freq="ME")
    bars = {}
    for ticker in ["AAPL", "SPY"]:
        bars[ticker] = pd.DataFrame({
            "symbol": [ticker] * len(dates),
            "timestamp": dates,
            "open": [100.0] * len(dates),
            "high": [105.0] * len(dates),
            "low": [95.0] * len(dates),
            "close": [100.0 + i for i in range(len(dates))],
            "volume": [1000000] * len(dates),
        })

    loop = ResearchLoop(
        tickers=["AAPL"], bars=bars,
        strategies_dir=strategies_dir, db_path=db_path,
    )

    # Mock proposer so it doesn't call Anthropic
    call_count = 0
    def mock_propose(context):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            loop.shutdown_requested = True
        return None

    loop.proposer = MagicMock()
    loop.proposer.propose.side_effect = mock_propose

    results = loop.run(max_iterations=10)
    # Should stop after ~2 iterations due to shutdown flag
    assert len(results) <= 3

    # State should be saved
    storage = Storage(db_path)
    state = storage.get_loop_state()
    storage.close()
    assert state is not None
    assert state["status"] == "stopped"
