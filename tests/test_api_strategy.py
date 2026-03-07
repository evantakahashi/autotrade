# tests/test_api_strategy.py
import pytest
import yaml
from pathlib import Path
from fastapi.testclient import TestClient
from src.data.db import Storage


@pytest.fixture
def setup(tmp_path):
    db_path = str(tmp_path / "test.duckdb")
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir()

    # Write a strategy file
    config = {
        "version": "0.1",
        "name": "baseline",
        "weights": {"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                    "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
        "thresholds": {"buy": 70, "sell": 40},
        "filters": {"min_price": 5.0, "min_avg_volume": 500000},
    }
    (strategies_dir / "v0.1.yaml").write_text(yaml.dump(config))

    db = Storage(db_path)
    db.store_strategy_version("0.1", "abc123", {"sharpe": 0.8, "cagr": 0.12})
    db.close()

    # Reset deps global to avoid stale connections
    from src.api import deps
    deps._db = None

    from src.api.server import create_app
    app = create_app(db_path=db_path, strategies_dir=str(strategies_dir))
    client = TestClient(app)
    return client


def test_get_current_strategy(setup):
    resp = setup.get("/api/strategy/current")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "0.1"
    assert "weights" in data
    assert "metrics" in data


def test_get_strategy_history(setup):
    resp = setup.get("/api/strategy/history")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["version"] == "0.1"
