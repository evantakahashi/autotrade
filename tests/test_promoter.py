# tests/test_promoter.py
from unittest.mock import MagicMock, patch
from src.research.promoter import Promoter

def _passing_verdict():
    return {
        "overall": "pass",
        "gates": [
            {"name": "sharpe", "passed": True, "detail": "1.2 > 1.0"},
            {"name": "walk_forward", "passed": True, "detail": "4/4"},
            {"name": "drawdown", "passed": True, "detail": "ok"},
            {"name": "turnover", "passed": True, "detail": "ok"},
            {"name": "regime_diversity", "passed": True, "detail": "ok"},
            {"name": "paper_trading", "passed": True, "detail": "stubbed"},
        ],
        "failed_gates": [],
    }

def _failing_verdict():
    return {
        "overall": "fail",
        "gates": [
            {"name": "sharpe", "passed": False, "detail": "0.8 < 1.0"},
            {"name": "walk_forward", "passed": True, "detail": "3/4"},
        ],
        "failed_gates": ["sharpe"],
    }

def test_auto_reject_on_gate_failure():
    promoter = Promoter()
    decision = promoter.decide(_failing_verdict(), "exp-001", {"weights": {"trend": 0.40}})
    assert decision["decision"] == "rejected"
    assert "sharpe" in decision["reasoning"].lower()

def test_promote_on_all_gates_pass():
    """After M5, all-gates-pass returns paper_testing (not promoted directly)."""
    promoter = Promoter()
    decision = promoter.decide(_passing_verdict(), "exp-001", {"weights": {"trend": 0.40}})
    assert decision["decision"] == "paper_testing"
    assert decision["reasoning"] != ""

def test_reject_does_not_call_llm():
    with patch("src.research.promoter.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        promoter = Promoter()
        promoter.decide(_failing_verdict(), "exp-001", {})
        # LLM should NOT be called for rejections
        mock_client.messages.create.assert_not_called()
