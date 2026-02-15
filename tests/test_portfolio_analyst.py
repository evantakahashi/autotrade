# tests/test_portfolio_analyst.py
import pandas as pd
import numpy as np
from datetime import datetime
from src.agents.portfolio_analyst import PortfolioAnalyst
from src.strategy.config import StrategyConfig

def _make_config():
    return StrategyConfig(
        version="0.1", name="test",
        weights={"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                 "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
        thresholds={"buy": 70, "hold_min": 40, "sell": 40},
        filters={},
    )

def _make_strong_bars(days=252):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    prices = 100 * np.cumprod(1 + np.random.normal(0.002, 0.008, days))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices,
        "volume": np.random.randint(1_000_000, 3_000_000, days),
    })

def _make_weak_bars(days=252):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    prices = 100 * np.cumprod(1 + np.random.normal(-0.002, 0.015, days))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 1.01, "high": prices * 1.02,
        "low": prices * 0.98, "close": prices,
        "volume": np.random.randint(100_000, 300_000, days),
    })

def test_analyze_returns_recommendations():
    analyst = PortfolioAnalyst(_make_config())
    spy = _make_strong_bars()
    bars = {"STRONG": _make_strong_bars(), "WEAK": _make_weak_bars(), "SPY": spy}
    recs = analyst.analyze(["STRONG", "WEAK"], bars)
    assert len(recs) == 2
    assert all(r.action in ("buy", "hold", "sell") for r in recs)

def test_strong_stock_scores_higher():
    analyst = PortfolioAnalyst(_make_config())
    spy = _make_strong_bars()
    bars = {"STRONG": _make_strong_bars(), "WEAK": _make_weak_bars(), "SPY": spy}
    recs = analyst.analyze(["STRONG", "WEAK"], bars)
    rec_map = {r.ticker: r for r in recs}
    assert rec_map["STRONG"].composite_score > rec_map["WEAK"].composite_score

def test_recommendation_has_required_fields():
    analyst = PortfolioAnalyst(_make_config())
    bars = {"AAPL": _make_strong_bars(), "SPY": _make_strong_bars()}
    recs = analyst.analyze(["AAPL"], bars)
    rec = recs[0]
    assert rec.rationale != ""
    assert rec.invalidation != ""
    assert "stop_loss" in rec.risk_params
