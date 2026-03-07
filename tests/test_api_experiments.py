# tests/test_api_experiments.py
import pytest
import json
import yaml
from datetime import date
from pathlib import Path
from fastapi.testclient import TestClient
from src.data.db import Storage


@pytest.fixture
def setup(tmp_path):
    db_path = str(tmp_path / "test.duckdb")
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir()
    config = {
        "version": "0.1", "name": "baseline",
        "weights": {"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                    "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
        "thresholds": {"buy": 70, "sell": 40},
    }
    (strategies_dir / "v0.1.yaml").write_text(yaml.dump(config))

    db = Storage(db_path)
    db.store_experiment("exp-001", "0.1", {"weights": {"trend": 0.40}}, "increase trend weight")
    db.update_experiment_decision("exp-001", "rejected", {"sharpe": 0.5})
    db.store_experiment("exp-002", "0.1", {"thresholds": {"buy": 75}}, "raise buy threshold")
    db.update_experiment_decision("exp-002", "promoted", {"sharpe": 1.2})
    # Paper trades for exp-002
    for i in range(5):
        db.store_paper_trade("exp-002", date(2026, 3, i + 1), {}, {},
                             0.005, 0.008, 0.005 * (i + 1), 0.008 * (i + 1))
    db.close()

    from src.api import deps
    deps._db = None

    from src.api.server import create_app
    app = create_app(db_path=db_path, strategies_dir=str(strategies_dir))
    return TestClient(app)


def test_list_experiments(setup):
    resp = setup.get("/api/experiments?last=10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_get_experiment(setup):
    resp = setup.get("/api/experiments/exp-001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["experiment_id"] == "exp-001"
    assert data["decision"] == "rejected"


def test_get_experiment_not_found(setup):
    resp = setup.get("/api/experiments/exp-999")
    assert resp.status_code == 404


def test_get_paper_trades(setup):
    resp = setup.get("/api/experiments/exp-002/paper-trades")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 5
