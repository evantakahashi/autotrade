# tests/test_auditor_no_paper_stub.py
import pytest
from src.research.auditor import evaluate_gates
from src.research.results import BacktestResult, WindowResult


def _make_result(sharpe: float, max_dd: float = 0.1, turnover: float = 0.1) -> BacktestResult:
    return BacktestResult(
        strategy_version="test",
        window_results=[
            WindowResult(window_id=i, train_start="", train_end="", test_start="", test_end="",
                         metrics={"sharpe": sharpe, "max_drawdown": max_dd, "monthly_turnover": turnover})
            for i in range(4)
        ],
        aggregate_metrics={"sharpe": sharpe, "max_drawdown": max_dd, "monthly_turnover": turnover},
    )


def test_no_paper_trading_gate_in_evaluate_gates():
    """evaluate_gates should NOT include paper_trading gate — it's handled separately now."""
    baseline = _make_result(0.5)
    experiment = _make_result(1.0)
    verdict = evaluate_gates(baseline, experiment)
    gate_names = [g["name"] for g in verdict["gates"]]
    assert "paper_trading" not in gate_names
    # Should have exactly 5 gates now
    assert len(verdict["gates"]) == 5
