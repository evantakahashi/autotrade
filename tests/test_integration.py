# tests/test_integration.py
"""End-to-end test: mock data -> scoring -> recommendations -> output."""
import pandas as pd
import numpy as np
from datetime import datetime
from src.agents.portfolio_analyst import PortfolioAnalyst
from src.agents.risk_manager import RiskManager
from src.strategy.config import StrategyConfig
from src.models.types import PortfolioReport
from src.output.console import format_report
from src.output.json_writer import write_report

def _config():
    return StrategyConfig(
        version="0.1", name="test",
        weights={"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                 "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
        thresholds={"buy": 70, "hold_min": 40, "sell": 40},
        filters={},
    )

def _synthetic_bars(ticker, daily_return=0.001, vol_mult=1.0, days=252):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    prices = 100 * np.cumprod(1 + np.random.normal(daily_return, 0.01 * vol_mult, days))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices,
        "volume": np.random.randint(500_000, 3_000_000, days),
    })

def test_full_pipeline():
    config = _config()
    bars = {
        "STRONG": _synthetic_bars("STRONG", daily_return=0.002),
        "MID":    _synthetic_bars("MID", daily_return=0.0005),
        "WEAK":   _synthetic_bars("WEAK", daily_return=-0.001, vol_mult=2.0),
        "SPY":    _synthetic_bars("SPY", daily_return=0.0005),
    }

    analyst = PortfolioAnalyst(config)
    recs = analyst.analyze(["STRONG", "MID", "WEAK"], bars)

    assert len(recs) == 3
    assert all(r.action in ("buy", "hold", "sell") for r in recs)
    assert all(0 <= r.composite_score <= 100 for r in recs)
    assert all(r.rationale != "" for r in recs)

    # STRONG should generally score highest
    rec_map = {r.ticker: r for r in recs}
    assert rec_map["STRONG"].composite_score > rec_map["WEAK"].composite_score

    # Risk review
    risk_mgr = RiskManager()
    warnings = risk_mgr.review(recs, thresholds=config.thresholds)
    assert isinstance(warnings, list)

    # Output
    report = PortfolioReport(
        date=datetime.now(), strategy_version=config.version,
        recommendations=recs, warnings=warnings,
        strongest=recs[0].ticker, weakest=recs[-1].ticker,
    )
    output = format_report(report)
    assert "STRONG" in output

def test_json_output(tmp_path):
    config = _config()
    bars = {
        "AAPL": _synthetic_bars("AAPL"),
        "SPY": _synthetic_bars("SPY"),
    }
    analyst = PortfolioAnalyst(config)
    recs = analyst.analyze(["AAPL"], bars)
    report = PortfolioReport(
        date=datetime.now(), strategy_version="0.1",
        recommendations=recs, warnings=[],
    )
    filepath = write_report(report, str(tmp_path))
    assert "analysis-" in filepath
