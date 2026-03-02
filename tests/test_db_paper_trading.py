# tests/test_db_paper_trading.py
import pytest
from datetime import datetime, date
from src.data.db import Storage


@pytest.fixture
def db(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    yield db
    db.close()


def test_store_and_get_paper_trade(db):
    db.store_paper_trade(
        experiment_id="exp-001",
        trade_date=date(2026, 3, 1),
        baseline_positions={"AAPL": "buy", "MSFT": "hold"},
        experiment_positions={"AAPL": "buy", "MSFT": "buy"},
        baseline_return=0.01,
        experiment_return=0.015,
        baseline_cumulative=0.01,
        experiment_cumulative=0.015,
    )
    trades = db.get_paper_trades("exp-001")
    assert len(trades) == 1
    assert trades[0]["experiment_id"] == "exp-001"
    assert trades[0]["experiment_return"] == 0.015


def test_get_paper_trades_empty(db):
    trades = db.get_paper_trades("exp-999")
    assert trades == []


def test_paper_trade_count(db):
    for i in range(5):
        db.store_paper_trade(
            experiment_id="exp-001",
            trade_date=date(2026, 3, i + 1),
            baseline_positions={}, experiment_positions={},
            baseline_return=0.01, experiment_return=0.02,
            baseline_cumulative=0.01 * (i + 1), experiment_cumulative=0.02 * (i + 1),
        )
    assert db.get_paper_trade_count("exp-001") == 5
    assert db.get_paper_trade_count("exp-999") == 0


def test_store_and_get_loop_state(db):
    db.save_loop_state(
        status="running",
        paper_trading_experiment="exp-001",
        paper_start_date=date(2026, 3, 1),
        consecutive_rejections=3,
    )
    state = db.get_loop_state()
    assert state is not None
    assert state["status"] == "running"
    assert state["paper_trading_experiment"] == "exp-001"
    assert state["consecutive_rejections"] == 3


def test_update_loop_state(db):
    db.save_loop_state(status="running", consecutive_rejections=0)
    db.save_loop_state(status="paused", consecutive_rejections=10)
    state = db.get_loop_state()
    assert state["status"] == "paused"
    assert state["consecutive_rejections"] == 10


def test_get_loop_state_empty(db):
    state = db.get_loop_state()
    assert state is None


def test_invalidate_inflight_experiments(db):
    db.store_experiment("exp-001", "0.1", {"weights": {"trend": 0.40}}, "hyp 1")
    db.update_experiment_decision("exp-001", "rejected", {})
    db.store_experiment("exp-002", "0.1", {"weights": {"trend": 0.35}}, "hyp 2")
    # exp-002 has no decision yet (in-flight)
    db.store_experiment("exp-003", "0.1", {"weights": {"trend": 0.30}}, "hyp 3")
    db.update_experiment_decision("exp-003", "paper_testing", {})

    db.invalidate_inflight_experiments(exclude_id="exp-003")
    exp2 = db.get_experiment("exp-002")
    assert exp2["decision"] == "invalidated"
    # exp-001 already had a decision, should be unchanged
    exp1 = db.get_experiment("exp-001")
    assert exp1["decision"] == "rejected"
    # exp-003 was excluded
    exp3 = db.get_experiment("exp-003")
    assert exp3["decision"] == "paper_testing"
