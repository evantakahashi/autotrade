# tests/test_loop_paper_trading.py
import pytest
import pandas as pd
from datetime import date, datetime
from unittest.mock import patch, MagicMock
from src.data.db import Storage
from src.research.loop import ResearchLoop


@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "test.duckdb")


@pytest.fixture
def dummy_bars():
    # 24 months of data across 2023-2024
    dates = pd.date_range("2023-01-15", periods=24, freq="ME")
    bars = {}
    for ticker in ["AAPL", "MSFT", "SPY"]:
        bars[ticker] = pd.DataFrame({
            "symbol": [ticker] * len(dates),
            "timestamp": dates,
            "open": [100.0] * len(dates),
            "high": [105.0] * len(dates),
            "low": [95.0] * len(dates),
            "close": [100.0 + i * 0.5 for i in range(len(dates))],
            "volume": [1000000] * len(dates),
        })
    return bars


def test_loop_checks_paper_trading_on_startup(db, dummy_bars, tmp_path):
    """If an experiment is in paper_testing state on startup, loop should detect it."""
    storage = Storage(db)
    storage.store_experiment("exp-001", "0.1", {"weights": {"trend": 0.40}}, "test hyp")
    storage.update_experiment_decision("exp-001", "paper_testing", {"sharpe": 1.0})
    storage.save_loop_state(
        status="running",
        paper_trading_experiment="exp-001",
        paper_start_date=date(2026, 2, 25),
        consecutive_rejections=0,
    )
    storage.close()

    strategies_dir = str(tmp_path / "strategies")
    import os, shutil
    os.makedirs(strategies_dir, exist_ok=True)
    shutil.copy("strategies/v0.1.yaml", f"{strategies_dir}/v0.1.yaml")

    loop = ResearchLoop(
        tickers=["AAPL", "MSFT"], bars=dummy_bars,
        strategies_dir=strategies_dir, db_path=db,
    )
    assert loop.paper_trading_experiment == "exp-001"
    loop.db.close()


def test_loop_saves_state_each_iteration(db, dummy_bars, tmp_path):
    """Loop should save state to DB after each iteration."""
    strategies_dir = str(tmp_path / "strategies")
    import os, shutil
    os.makedirs(strategies_dir, exist_ok=True)
    shutil.copy("strategies/v0.1.yaml", f"{strategies_dir}/v0.1.yaml")

    loop = ResearchLoop(
        tickers=["AAPL", "MSFT"], bars=dummy_bars,
        strategies_dir=strategies_dir, db_path=db,
    )

    # Mock proposer to return None (skip) so iteration is fast
    loop.proposer = MagicMock()
    loop.proposer.propose.return_value = None

    loop.run(max_iterations=1)

    storage = Storage(db)
    state = storage.get_loop_state()
    storage.close()
    assert state is not None
    assert state["status"] in ("running", "stopped")
