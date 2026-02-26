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
