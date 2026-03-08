# tests/test_api_loop.py
import pytest
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
    db.save_loop_state(
        status="running",
        paper_trading_experiment="exp-003",
        paper_start_date=date(2026, 3, 1),
        consecutive_rejections=3,
    )
    db.close()

    from src.api import deps
    deps._db = None

    from src.api.server import create_app
    app = create_app(db_path=db_path, strategies_dir=str(strategies_dir))
    return TestClient(app)


def test_get_loop_status(setup):
    resp = setup.get("/api/loop/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert data["paper_trading_experiment"] == "exp-003"
    assert data["consecutive_rejections"] == 3
    assert "process_alive" in data


def test_get_loop_status_empty(tmp_path):
    db_path = str(tmp_path / "empty.duckdb")
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir()
    config = {
        "version": "0.1", "name": "baseline",
        "weights": {"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                    "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
        "thresholds": {"buy": 70, "sell": 40},
    }
    (strategies_dir / "v0.1.yaml").write_text(yaml.dump(config))

    from src.api import deps
    deps._db = None

    from src.api.server import create_app
    app = create_app(db_path=db_path, strategies_dir=str(strategies_dir))
    client = TestClient(app)
    resp = client.get("/api/loop/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "stopped"


def test_stop_loop_no_process(setup):
    resp = setup.post("/api/loop/stop")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "no process running"
