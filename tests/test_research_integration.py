# tests/test_research_integration.py
"""End-to-end: mock LLM -> propose -> backtest -> evaluate -> reject/promote."""
import yaml
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import MagicMock, patch
from src.research.loop import ResearchLoop

def _synthetic_bars(days=504):
    end = datetime(2026, 1, 1)
    dates = pd.date_range(end=end, periods=days, freq="B")
    bars = {}
    for t in ["AAPL", "MSFT", "GOOG", "SPY"]:
        np.random.seed(hash(t) % 2**31)
        prices = 100 * np.cumprod(1 + np.random.normal(0.0005, 0.012, days))
        bars[t] = pd.DataFrame({
            "timestamp": dates, "open": prices * 0.99, "high": prices * 1.01,
            "low": prices * 0.98, "close": prices,
            "volume": np.random.randint(500_000, 3_000_000, days),
        })
    return bars

def test_full_research_iteration(tmp_path):
    mock_proposal = {
        "config_diff": {"weights": {"trend": 0.40, "fundamentals": 0.15}},
        "hypothesis": "Increase trend weight to capture stronger momentum",
    }

    with patch("src.research.loop.Proposer") as MockProposer, \
         patch("src.research.loop.Promoter") as MockPromoter:

        mock_proposer = MagicMock()
        mock_proposer.propose.return_value = mock_proposal
        MockProposer.return_value = mock_proposer

        mock_promoter = MagicMock()
        mock_promoter.decide.return_value = {"decision": "rejected", "reasoning": "Sharpe decreased"}
        MockPromoter.return_value = mock_promoter

        # Setup
        strategies_dir = tmp_path / "strategies"
        strategies_dir.mkdir()
        baseline = {
            "version": "0.1", "name": "baseline",
            "weights": {"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                        "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
            "thresholds": {"buy": 70, "hold_min": 40, "sell": 40},
            "filters": {},
            "backtest": {"train_months": 4, "validation_months": 1,
                         "test_months": 1, "step_months": 1,
                         "rebalance_frequency": "weekly", "transaction_cost_bps": 10},
        }
        (strategies_dir / "v0.1.yaml").write_text(yaml.dump(baseline))

        loop = ResearchLoop(
            tickers=["AAPL", "MSFT", "GOOG"],
            bars=_synthetic_bars(),
            strategies_dir=str(strategies_dir),
            experiments_dir=str(tmp_path / "experiments"),
            db_path=str(tmp_path / "test.duckdb"),
            max_consecutive_rejections=2,
        )

        results = loop.run(max_iterations=3)

        assert len(results) == 2  # stops at 2 consecutive rejections
        assert all(r["decision"] == "rejected" for r in results)

        # Verify experiment files were created
        exp_dirs = list((tmp_path / "experiments").iterdir())
        assert len(exp_dirs) == 2
        for d in exp_dirs:
            assert (d / "config.yaml").exists()
            assert (d / "hypothesis.md").exists()
            assert (d / "decision.md").exists()
