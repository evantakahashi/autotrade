# tests/test_api_integration.py
"""Verify all API endpoints work together."""
import pytest
import yaml
from datetime import datetime, date
from pathlib import Path
from fastapi.testclient import TestClient
from src.data.db import Storage


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.duckdb")
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir()

    config = {
        "version": "0.1", "name": "baseline",
        "weights": {"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                    "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
        "thresholds": {"buy": 70, "sell": 40},
        "filters": {"min_price": 5.0},
    }
    (strategies_dir / "v0.1.yaml").write_text(yaml.dump(config))

    db = Storage(db_path)
    db.store_strategy_version("0.1", "abc123", {"sharpe": 0.8, "cagr": 0.12})
    db.store_experiment("exp-001", "0.1", {"weights": {"trend": 0.40}}, "increase trend weight")
    db.update_experiment_decision("exp-001", "rejected", {"sharpe": 0.5})
    db.store_experiment("exp-002", "0.1", {"thresholds": {"buy": 75}}, "raise buy threshold")
    db.update_experiment_decision("exp-002", "promoted", {"sharpe": 1.2})
    for i in range(3):
        db.store_paper_trade("exp-002", date(2026, 3, i + 1), {}, {},
                             0.005, 0.008, 0.005 * (i + 1), 0.008 * (i + 1))
    db.store_score(datetime(2026, 3, 1), "AAPL", "trend", 75.0, 0.8, {"momentum": 80})
    db.save_loop_state(status="running", consecutive_rejections=2)
    db.close()

    from src.api import deps
    deps._db = None

    from src.api.server import create_app
    app = create_app(db_path=db_path, strategies_dir=str(strategies_dir))
    return TestClient(app)


def test_all_get_endpoints(client):
    """All read endpoints return 200 with valid JSON."""
    endpoints = [
        "/api/strategy/current",
        "/api/strategy/history",
        "/api/experiments?last=10",
        "/api/experiments/exp-001",
        "/api/experiments/exp-002/paper-trades",
        "/api/scores/AAPL?last=10",
        "/api/loop/status",
    ]
    for ep in endpoints:
        resp = client.get(ep)
        assert resp.status_code == 200, f"{ep} returned {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data is not None, f"{ep} returned None"


def test_experiment_404(client):
    resp = client.get("/api/experiments/nonexistent")
    assert resp.status_code == 404


def test_strategy_current_has_metrics(client):
    resp = client.get("/api/strategy/current")
    data = resp.json()
    assert data["version"] == "0.1"
    assert data["metrics"]["sharpe"] == 0.8


def test_experiments_list_order(client):
    resp = client.get("/api/experiments?last=10")
    data = resp.json()
    assert len(data) == 2
    # Most recent first
    assert data[0]["experiment_id"] == "exp-002"


def test_loop_status_fields(client):
    resp = client.get("/api/loop/status")
    data = resp.json()
    assert data["status"] == "running"
    assert data["consecutive_rejections"] == 2
    assert "process_alive" in data
