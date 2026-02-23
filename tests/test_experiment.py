# tests/test_experiment.py
import json
from pathlib import Path
from src.research.experiment import ExperimentManager
from src.data.db import Storage

def test_create_experiment(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    mgr = ExperimentManager(db, experiments_dir=str(tmp_path / "experiments"))
    exp = mgr.create(
        parent_version="0.1",
        config_diff={"weights": {"trend": 0.40, "fundamentals": 0.15}},
        hypothesis="Increase trend weight to capture stronger momentum",
    )
    assert exp["experiment_id"] == "exp-001"
    assert (tmp_path / "experiments" / "exp-001-increase-trend-weight").exists()
    assert (tmp_path / "experiments" / "exp-001-increase-trend-weight" / "config.yaml").exists()
    assert (tmp_path / "experiments" / "exp-001-increase-trend-weight" / "hypothesis.md").exists()

def test_sequential_ids(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    mgr = ExperimentManager(db, experiments_dir=str(tmp_path / "experiments"))
    e1 = mgr.create("0.1", {"weights": {"trend": 0.40}}, "first")
    e2 = mgr.create("0.1", {"weights": {"trend": 0.45}}, "second")
    assert e1["experiment_id"] == "exp-001"
    assert e2["experiment_id"] == "exp-002"

def test_record_decision(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    mgr = ExperimentManager(db, experiments_dir=str(tmp_path / "experiments"))
    exp = mgr.create("0.1", {"weights": {"trend": 0.40}}, "test")
    mgr.record_decision(
        exp["experiment_id"], exp["dir_name"],
        decision="rejected",
        metrics={"sharpe": 0.8},
        reasoning="Sharpe decreased",
    )
    # Check DB
    stored = db.get_experiment(exp["experiment_id"])
    assert stored["decision"] == "rejected"
    # Check file
    decision_file = tmp_path / "experiments" / exp["dir_name"] / "decision.md"
    assert decision_file.exists()
    assert "rejected" in decision_file.read_text().lower()

def test_get_next_id(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    mgr = ExperimentManager(db, experiments_dir=str(tmp_path / "experiments"))
    assert mgr._next_id() == "exp-001"
    mgr.create("0.1", {}, "test")
    assert mgr._next_id() == "exp-002"
