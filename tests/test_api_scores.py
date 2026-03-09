# tests/test_api_scores.py
import pytest
import yaml
from datetime import datetime
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
    db.store_score(datetime(2026, 3, 1), "AAPL", "trend", 75.0, 0.8, {"momentum": 80})
    db.store_score(datetime(2026, 3, 1), "AAPL", "volatility", 60.0, 0.7, {"vol": 25})
    db.store_score(datetime(2026, 3, 2), "AAPL", "trend", 72.0, 0.75, {"momentum": 76})
    db.close()

    from src.api import deps
    deps._db = None

    from src.api.server import create_app
    app = create_app(db_path=db_path, strategies_dir=str(strategies_dir))
    return TestClient(app)


def test_get_scores(setup):
    resp = setup.get("/api/scores/AAPL?last=10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    assert all(s["ticker"] == "AAPL" for s in data)


def test_get_scores_empty(setup):
    resp = setup.get("/api/scores/UNKNOWN?last=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data == []
