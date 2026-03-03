# tests/test_paper_trader.py
import pytest
import pandas as pd
import numpy as np
from datetime import date, datetime
from unittest.mock import MagicMock
from src.data.db import Storage
from src.research.paper_trader import PaperTrader


@pytest.fixture
def db(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    yield db
    db.close()


def _make_bars(ticker: str, dates: list, closes: list) -> pd.DataFrame:
    """Helper to create bars DataFrame."""
    return pd.DataFrame({
        "symbol": [ticker] * len(dates),
        "timestamp": [pd.Timestamp(d) for d in dates],
        "open": closes,
        "high": [c * 1.01 for c in closes],
        "low": [c * 0.99 for c in closes],
        "close": closes,
        "volume": [1000000] * len(dates),
    })


def test_record_day_computes_returns(db):
    dates = [f"2026-03-{d:02d}" for d in range(1, 12)]
    bars = {
        "AAPL": _make_bars("AAPL", dates, [100 + i for i in range(11)]),
        "MSFT": _make_bars("MSFT", dates, [200 + i * 2 for i in range(11)]),
        "SPY": _make_bars("SPY", dates, [400 + i for i in range(11)]),
    }

    # Mock runner that returns fixed positions
    baseline_runner = MagicMock()
    baseline_runner.get_positions.return_value = {
        "AAPL": {"action": "buy", "composite_score": 75},
        "MSFT": {"action": "hold", "composite_score": 55},
    }
    experiment_runner = MagicMock()
    experiment_runner.get_positions.return_value = {
        "AAPL": {"action": "buy", "composite_score": 80},
        "MSFT": {"action": "buy", "composite_score": 72},
    }

    trader = PaperTrader(
        db=db,
        experiment_id="exp-001",
        tickers=["AAPL", "MSFT"],
        bars=bars,
        baseline_runner=baseline_runner,
        experiment_runner=experiment_runner,
    )

    result = trader.record_day(date(2026, 3, 10))
    assert result is not None
    assert "baseline_return" in result
    assert "experiment_return" in result
    assert "baseline_cumulative" in result
    assert "experiment_cumulative" in result

    # Should have stored in DB
    trades = db.get_paper_trades("exp-001")
    assert len(trades) == 1


def test_record_multiple_days_cumulative(db):
    dates = [f"2026-03-{d:02d}" for d in range(1, 15)]
    # AAPL goes up, MSFT flat
    bars = {
        "AAPL": _make_bars("AAPL", dates, [100 + i * 2 for i in range(14)]),
        "MSFT": _make_bars("MSFT", dates, [200] * 14),
        "SPY": _make_bars("SPY", dates, [400] * 14),
    }

    baseline_runner = MagicMock()
    baseline_runner.get_positions.return_value = {
        "AAPL": {"action": "buy", "composite_score": 75},
    }
    experiment_runner = MagicMock()
    experiment_runner.get_positions.return_value = {
        "AAPL": {"action": "buy", "composite_score": 80},
        "MSFT": {"action": "buy", "composite_score": 70},
    }

    trader = PaperTrader(
        db=db, experiment_id="exp-001", tickers=["AAPL", "MSFT"],
        bars=bars, baseline_runner=baseline_runner,
        experiment_runner=experiment_runner,
    )

    trader.record_day(date(2026, 3, 10))
    trader.record_day(date(2026, 3, 11))
    trader.record_day(date(2026, 3, 12))

    trades = db.get_paper_trades("exp-001")
    assert len(trades) == 3
    # Cumulative should be monotonically tracked
    cums = [t["experiment_cumulative"] for t in trades]
    assert len(cums) == 3


def test_evaluate_gate_pass(db):
    # Simulate 10 days where experiment beats baseline
    for i in range(10):
        db.store_paper_trade(
            experiment_id="exp-001",
            trade_date=date(2026, 3, i + 1),
            baseline_positions={}, experiment_positions={},
            baseline_return=0.005, experiment_return=0.008,
            baseline_cumulative=0.005 * (i + 1),
            experiment_cumulative=0.008 * (i + 1),
        )
    result = PaperTrader.evaluate_gate("exp-001", db, max_underperformance=0.01)
    assert result["passed"] is True
    assert result["experiment_cumulative"] > 0
    assert result["beat_baseline"] is True


def test_evaluate_gate_fail_negative_return(db):
    # Experiment has negative return
    for i in range(10):
        db.store_paper_trade(
            experiment_id="exp-001",
            trade_date=date(2026, 3, i + 1),
            baseline_positions={}, experiment_positions={},
            baseline_return=0.005, experiment_return=-0.003,
            baseline_cumulative=0.005 * (i + 1),
            experiment_cumulative=-0.003 * (i + 1),
        )
    result = PaperTrader.evaluate_gate("exp-001", db)
    assert result["passed"] is False
    assert "negative return" in result["reason"].lower()


def test_evaluate_gate_fail_underperformance(db):
    # Experiment underperforms baseline by more than 1%
    for i in range(10):
        db.store_paper_trade(
            experiment_id="exp-001",
            trade_date=date(2026, 3, i + 1),
            baseline_positions={}, experiment_positions={},
            baseline_return=0.01, experiment_return=0.005,
            baseline_cumulative=0.01 * (i + 1),
            experiment_cumulative=0.005 * (i + 1),
        )
    result = PaperTrader.evaluate_gate("exp-001", db, max_underperformance=0.01)
    assert result["passed"] is False
    assert "underperform" in result["reason"].lower()
