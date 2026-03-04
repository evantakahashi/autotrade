# tests/test_loop.py
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import MagicMock, patch
from src.research.loop import ResearchLoop

def _synthetic_bars(days=504):
    end = datetime(2026, 1, 1)
    dates = pd.date_range(end=end, periods=days, freq="B")
    bars = {}
    for t in ["AAPL", "MSFT", "SPY"]:
        np.random.seed(hash(t) % 2**31)
        prices = 100 * np.cumprod(1 + np.random.normal(0.0005, 0.012, days))
        bars[t] = pd.DataFrame({
            "timestamp": dates, "open": prices * 0.99, "high": prices * 1.01,
            "low": prices * 0.98, "close": prices,
            "volume": np.random.randint(500_000, 3_000_000, days),
        })
    return bars

def test_loop_single_iteration(tmp_path):
    """Mock the LLM calls, run one iteration of the loop."""
    # Mock proposer to return a valid proposal
    mock_proposal = {
        "config_diff": {"weights": {"trend": 0.40, "fundamentals": 0.15}},
        "hypothesis": "Test: increase trend weight",
    }

    with patch("src.research.loop.Proposer") as MockProposer, \
         patch("src.research.loop.Promoter") as MockPromoter:

        mock_proposer = MagicMock()
        mock_proposer.propose.return_value = mock_proposal
        MockProposer.return_value = mock_proposer

        mock_promoter = MagicMock()
        mock_promoter.decide_backtest.return_value = {"decision": "rejected", "reasoning": "test"}
        MockPromoter.return_value = mock_promoter

        loop = ResearchLoop(
            tickers=["AAPL", "MSFT"],
            bars=_synthetic_bars(),
            strategies_dir=str(tmp_path / "strategies"),
            experiments_dir=str(tmp_path / "experiments"),
            db_path=str(tmp_path / "test.duckdb"),
        )

        # Create baseline strategy
        import yaml
        (tmp_path / "strategies").mkdir()
        baseline = {
            "version": "0.1", "name": "baseline",
            "weights": {"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                        "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
            "thresholds": {"buy": 70, "hold_min": 40, "sell": 40},
            "filters": {}, "backtest": {"train_months": 4, "validation_months": 1,
                                         "test_months": 1, "step_months": 1,
                                         "rebalance_frequency": "weekly",
                                         "transaction_cost_bps": 10},
        }
        (tmp_path / "strategies" / "v0.1.yaml").write_text(yaml.dump(baseline))

        result = loop.run_one_iteration()
        assert result["experiment_id"] is not None
        assert result["decision"] in ("rejected", "promoted", "paper_testing")

def test_loop_stops_after_max_rejections(tmp_path):
    mock_proposal = {
        "config_diff": {"weights": {"trend": 0.40, "fundamentals": 0.15}},
        "hypothesis": "test",
    }

    with patch("src.research.loop.Proposer") as MockProposer, \
         patch("src.research.loop.Promoter") as MockPromoter:

        mock_proposer = MagicMock()
        mock_proposer.propose.return_value = mock_proposal
        MockProposer.return_value = mock_proposer

        mock_promoter = MagicMock()
        mock_promoter.decide_backtest.return_value = {"decision": "rejected", "reasoning": "test"}
        MockPromoter.return_value = mock_promoter

        loop = ResearchLoop(
            tickers=["AAPL", "MSFT"],
            bars=_synthetic_bars(),
            strategies_dir=str(tmp_path / "strategies"),
            experiments_dir=str(tmp_path / "experiments"),
            db_path=str(tmp_path / "test.duckdb"),
            max_consecutive_rejections=3,
        )

        import yaml
        (tmp_path / "strategies").mkdir()
        baseline = {
            "version": "0.1", "name": "baseline",
            "weights": {"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                        "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
            "thresholds": {"buy": 70, "hold_min": 40, "sell": 40},
            "filters": {}, "backtest": {"train_months": 4, "validation_months": 1,
                                         "test_months": 1, "step_months": 1,
                                         "rebalance_frequency": "weekly",
                                         "transaction_cost_bps": 10},
        }
        (tmp_path / "strategies" / "v0.1.yaml").write_text(yaml.dump(baseline))

        results = loop.run(max_iterations=5)
        assert len(results) == 3  # stops after 3 consecutive rejections
