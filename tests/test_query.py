# tests/test_query.py
import json
import subprocess
import sys
import tempfile
import pytest
from src.data.db import Storage


@pytest.fixture
def db_with_experiments(tmp_path):
    db_path = str(tmp_path / "test.duckdb")
    db = Storage(db_path)
    db.store_experiment("exp-001", "0.1", {"weights": {"trend": 0.40}}, "increase trend weight")
    db.update_experiment_decision("exp-001", "rejected", {"sharpe": 0.5})
    db.store_experiment("exp-002", "0.1", {"thresholds": {"buy": 75}}, "raise buy threshold")
    db.update_experiment_decision("exp-002", "promoted", {"sharpe": 1.2})
    db.store_experiment("exp-003", "0.2", {"weights": {"volatility": 0.20}}, "increase vol weight")
    db.close()
    yield db_path


def test_experiments_last(db_with_experiments):
    result = subprocess.run(
        [sys.executable, "query.py", "experiments", "--last", "2", "--db", db_with_experiments],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data) == 2


def test_experiment_by_id(db_with_experiments):
    result = subprocess.run(
        [sys.executable, "query.py", "experiment", "--id", "exp-001", "--db", db_with_experiments],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["experiment_id"] == "exp-001"


def test_experiment_not_found(db_with_experiments):
    result = subprocess.run(
        [sys.executable, "query.py", "experiment", "--id", "exp-999", "--db", db_with_experiments],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "not found" in result.stderr.lower()


@pytest.fixture
def db_with_strategies(tmp_path):
    db_path = str(tmp_path / "test.duckdb")
    db = Storage(db_path)
    db.store_strategy_version("0.1", "abc123", {"sharpe": 0.8})
    db.store_strategy_version("0.2", "def456", {"sharpe": 1.1})
    db.close()
    yield db_path


def test_strategy_current(db_with_strategies):
    result = subprocess.run(
        [sys.executable, "query.py", "strategy", "--current", "--db", db_with_strategies],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["version"] == "0.2"


def test_strategy_history(db_with_strategies):
    result = subprocess.run(
        [sys.executable, "query.py", "strategy", "--history", "--db", db_with_strategies],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data) == 2


@pytest.fixture
def db_with_scores(tmp_path):
    from datetime import datetime
    db_path = str(tmp_path / "test.duckdb")
    db = Storage(db_path)
    db.store_score(datetime(2026, 3, 1), "AAPL", "trend", 75.0, 0.8, {"momentum": 80})
    db.store_score(datetime(2026, 3, 1), "AAPL", "volatility", 60.0, 0.7, {"vol": 25})
    db.store_score(datetime(2026, 3, 2), "AAPL", "trend", 72.0, 0.75, {"momentum": 76})
    db.close()
    yield db_path


def test_scores_by_ticker(db_with_scores):
    result = subprocess.run(
        [sys.executable, "query.py", "scores", "--ticker", "AAPL", "--last", "5", "--db", db_with_scores],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data) == 3
    assert all(r["ticker"] == "AAPL" for r in data)
