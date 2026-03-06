# tests/test_m5_integration.py
"""Verify M5 paper trading + hardening components work together."""
import pytest
import json
import subprocess
import sys
import pandas as pd
from datetime import date, datetime
from unittest.mock import MagicMock
from src.data.db import Storage
from src.research.paper_trader import PaperTrader
from src.research.promoter import Promoter
from src.research.auditor import evaluate_gates
from src.research.results import BacktestResult, WindowResult


@pytest.fixture
def db(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    yield db
    db.close()


def test_full_paper_trading_flow(db):
    """End-to-end: experiment passes backtest -> paper_testing -> evaluate -> promote/reject."""
    # 1. Simulate backtest gates passing
    baseline = BacktestResult("0.1", [
        WindowResult(i, "", "", "", "", metrics={"sharpe": 0.8, "max_drawdown": 0.1, "monthly_turnover": 0.1})
        for i in range(4)
    ], {"sharpe": 0.8, "max_drawdown": 0.1, "monthly_turnover": 0.1})

    experiment = BacktestResult("0.1-exp", [
        WindowResult(i, "", "", "", "", metrics={"sharpe": 1.2, "max_drawdown": 0.08, "monthly_turnover": 0.09})
        for i in range(4)
    ], {"sharpe": 1.2, "max_drawdown": 0.08, "monthly_turnover": 0.09})

    verdict = evaluate_gates(baseline, experiment)
    assert verdict["overall"] == "pass"
    assert "paper_trading" not in [g["name"] for g in verdict["gates"]]

    # 2. Promoter returns paper_testing
    promoter = Promoter()
    decision = promoter.decide_backtest(verdict, "exp-001", {"weights": {"trend": 0.40}})
    assert decision["decision"] == "paper_testing"

    # 3. Simulate 10 days of paper trading
    for i in range(10):
        db.store_paper_trade(
            experiment_id="exp-001",
            trade_date=date(2026, 3, i + 1),
            baseline_positions={"AAPL": "buy"},
            experiment_positions={"AAPL": "buy", "MSFT": "buy"},
            baseline_return=0.005,
            experiment_return=0.007,
            baseline_cumulative=0.005 * (i + 1),
            experiment_cumulative=0.007 * (i + 1),
        )

    # 4. Evaluate paper trading gate
    gate_result = PaperTrader.evaluate_gate("exp-001", db)
    assert gate_result["passed"] is True
    assert gate_result["days"] == 10

    # 5. Final promotion decision
    final = promoter.decide_paper(gate_result, "exp-001", {"weights": {"trend": 0.40}})
    assert final["decision"] == "promoted"


def test_paper_trading_rejection_flow(db):
    """Experiment passes backtest but fails paper trading -> rejected."""
    promoter = Promoter()

    # Simulate 10 days where experiment loses money
    for i in range(10):
        db.store_paper_trade(
            experiment_id="exp-002",
            trade_date=date(2026, 3, i + 1),
            baseline_positions={}, experiment_positions={},
            baseline_return=0.005, experiment_return=-0.003,
            baseline_cumulative=0.005 * (i + 1),
            experiment_cumulative=-0.003 * (i + 1),
        )

    gate_result = PaperTrader.evaluate_gate("exp-002", db)
    assert gate_result["passed"] is False

    final = promoter.decide_paper(gate_result, "exp-002", {"thresholds": {"buy": 75}})
    assert final["decision"] == "rejected"


def test_loop_state_persistence(tmp_path):
    """Loop state survives DB close/reopen."""
    db_path = str(tmp_path / "persist.duckdb")
    db = Storage(db_path)
    db.save_loop_state(
        status="running",
        paper_trading_experiment="exp-001",
        paper_start_date=date(2026, 3, 1),
        consecutive_rejections=5,
    )
    db.close()

    db2 = Storage(db_path)
    state = db2.get_loop_state()
    db2.close()
    assert state["status"] == "running"
    assert state["paper_trading_experiment"] == "exp-001"
    assert state["consecutive_rejections"] == 5


def test_invalidation_on_promotion(db):
    """In-flight experiments get invalidated when baseline changes."""
    db.store_experiment("exp-001", "0.1", {}, "promoted one")
    db.update_experiment_decision("exp-001", "promoted", {})
    db.store_experiment("exp-002", "0.1", {}, "in flight")
    # exp-002 has no decision (in-flight)
    db.store_experiment("exp-003", "0.1", {}, "paper testing")
    db.update_experiment_decision("exp-003", "paper_testing", {})

    db.invalidate_inflight_experiments(exclude_id="exp-003")

    assert db.get_experiment("exp-001")["decision"] == "promoted"
    assert db.get_experiment("exp-002")["decision"] == "invalidated"
    assert db.get_experiment("exp-003")["decision"] == "paper_testing"


def test_query_paper_trades_cli(db, tmp_path):
    """query.py paper-trades subcommand works."""
    db_path = str(tmp_path / "test2.duckdb")
    db2 = Storage(db_path)
    db2.store_paper_trade("exp-001", date(2026, 3, 1), {}, {}, 0.01, 0.02, 0.01, 0.02)
    db2.close()

    result = subprocess.run(
        [sys.executable, "query.py", "paper-trades", "--id", "exp-001", "--db", db_path],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
