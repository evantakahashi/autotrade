# tests/test_api_analyze.py
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from src.data.db import Storage
from src.models.types import Recommendation


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
        "filters": {"min_price": 5.0, "min_avg_volume": 500000},
    }
    (strategies_dir / "v0.1.yaml").write_text(yaml.dump(config))
    Storage(db_path).close()  # init tables

    from src.api import deps
    deps._db = None

    from src.api.server import create_app
    app = create_app(db_path=db_path, strategies_dir=str(strategies_dir))
    return TestClient(app)


def test_analyze_returns_recommendations(setup):
    mock_recs = [
        Recommendation(ticker="AAPL", action="buy", confidence=0.8,
                       composite_score=75.5, signal_scores={"trend": 80, "volatility": 70},
                       rationale="strong trend", invalidation="below 150",
                       risk_params={"stop_loss": 0.08}),
        Recommendation(ticker="MSFT", action="hold", confidence=0.6,
                       composite_score=55.0, signal_scores={"trend": 60, "volatility": 50},
                       rationale="mixed signals", invalidation="",
                       risk_params={}),
    ]

    with patch("src.api.routes.analyze.AlpacaProvider") as mock_provider_cls, \
         patch("src.api.routes.analyze.PortfolioAnalyst") as mock_analyst_cls, \
         patch("src.api.routes.analyze.RiskManager") as mock_risk_cls:

        mock_provider = MagicMock()
        mock_provider_cls.return_value = mock_provider
        import pandas as pd
        mock_provider.get_bars.return_value = pd.DataFrame({
            "symbol": ["AAPL"] * 5, "timestamp": pd.date_range("2026-01-01", periods=5),
            "open": [100]*5, "high": [105]*5, "low": [95]*5, "close": [100]*5, "volume": [1000000]*5,
        })

        mock_analyst = MagicMock()
        mock_analyst_cls.return_value = mock_analyst
        mock_analyst.analyze.return_value = mock_recs

        mock_risk = MagicMock()
        mock_risk_cls.return_value = mock_risk
        mock_risk.review.return_value = ["Borderline: MSFT at 55"]

        resp = setup.post("/api/analyze", json={"tickers": ["AAPL", "MSFT"]})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["recommendations"]) == 2
    assert data["recommendations"][0]["ticker"] == "AAPL"
    assert data["recommendations"][0]["action"] == "buy"
    assert len(data["warnings"]) == 1


def test_analyze_missing_tickers(setup):
    resp = setup.post("/api/analyze", json={})
    assert resp.status_code == 422
