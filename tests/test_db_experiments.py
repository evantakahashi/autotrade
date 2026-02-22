# tests/test_db_experiments.py
import json
from datetime import datetime
from src.data.db import Storage

def test_store_and_get_experiment(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    db.store_experiment(
        experiment_id="exp-001",
        parent_version="0.1",
        config_diff={"weights": {"trend": 0.40}},
        hypothesis="Increase trend weight",
    )
    experiments = db.get_experiments()
    assert len(experiments) == 1
    assert experiments[0]["experiment_id"] == "exp-001"

def test_update_experiment_decision(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    db.store_experiment("exp-001", "0.1", {}, "test")
    db.update_experiment_decision(
        "exp-001", decision="rejected",
        metrics={"sharpe": 0.8, "cagr": 0.05}
    )
    exp = db.get_experiment("exp-001")
    assert exp["decision"] == "rejected"

def test_get_recent_experiments(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    for i in range(5):
        db.store_experiment(f"exp-{i:03d}", "0.1", {}, f"hypothesis {i}")
    recent = db.get_recent_experiments(limit=3)
    assert len(recent) == 3

def test_store_strategy_version(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    db.store_strategy_version(
        version="0.2", config_hash="abc123",
        metrics={"sharpe": 1.2}
    )
    versions = db.get_strategy_versions()
    assert len(versions) == 1
    assert versions[0]["version"] == "0.2"

def test_get_baseline_version(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    db.store_strategy_version("0.1", "hash1", {"sharpe": 1.0})
    db.store_strategy_version("0.2", "hash2", {"sharpe": 1.2})
    latest = db.get_latest_strategy_version()
    assert latest["version"] == "0.2"
