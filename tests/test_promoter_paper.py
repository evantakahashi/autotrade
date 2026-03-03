# tests/test_promoter_paper.py
import pytest
from src.research.promoter import Promoter


def _all_pass_verdict():
    return {
        "overall": "pass",
        "gates": [
            {"name": "sharpe", "passed": True, "detail": "1.2 > 0.8"},
            {"name": "walk_forward", "passed": True, "detail": "4/4 windows"},
            {"name": "drawdown", "passed": True, "detail": "ok"},
            {"name": "turnover", "passed": True, "detail": "ok"},
            {"name": "regime_diversity", "passed": True, "detail": "ok"},
        ],
        "failed_gates": [],
    }


def _fail_verdict():
    return {
        "overall": "fail",
        "gates": [
            {"name": "sharpe", "passed": False, "detail": "0.5 < 0.8"},
        ],
        "failed_gates": ["sharpe"],
    }


def test_all_backtest_gates_pass_returns_paper_testing():
    promoter = Promoter()
    verdict = _all_pass_verdict()
    # Note: verdict has no paper_trading gate — backtest gates only
    result = promoter.decide_backtest(verdict, "exp-001", {"weights": {"trend": 0.40}})
    assert result["decision"] == "paper_testing"


def test_backtest_gate_fails_returns_rejected():
    promoter = Promoter()
    verdict = _fail_verdict()
    result = promoter.decide_backtest(verdict, "exp-001", {"weights": {"trend": 0.40}})
    assert result["decision"] == "rejected"


def test_paper_gate_pass_returns_promoted():
    promoter = Promoter()
    paper_result = {
        "passed": True,
        "experiment_cumulative": 0.05,
        "baseline_cumulative": 0.03,
        "beat_baseline": True,
        "directional_consistency": 0.7,
        "days": 10,
    }
    result = promoter.decide_paper(paper_result, "exp-001", {"weights": {"trend": 0.40}})
    assert result["decision"] == "promoted"


def test_paper_gate_fail_returns_rejected():
    promoter = Promoter()
    paper_result = {
        "passed": False,
        "reason": "Negative return",
        "experiment_cumulative": -0.02,
        "baseline_cumulative": 0.03,
        "beat_baseline": False,
        "directional_consistency": 0.3,
        "days": 10,
    }
    result = promoter.decide_paper(paper_result, "exp-001", {"weights": {"trend": 0.40}})
    assert result["decision"] == "rejected"
    assert "paper trading" in result["reasoning"].lower()
