# tests/test_context.py
from src.research.context import build_context_summary

def test_builds_summary_string():
    baseline_metrics = {"sharpe": 1.1, "cagr": 0.12, "max_drawdown": 0.08}
    baseline_config = {
        "weights": {"trend": 0.35, "relative_strength": 0.10},
        "thresholds": {"buy": 70, "sell": 40},
        "filters": {},
    }
    recent_experiments = [
        {"experiment_id": "exp-001", "config_diff": '{"weights": {"trend": 0.40}}',
         "decision": "rejected", "metrics": '{"sharpe": 0.9}'},
        {"experiment_id": "exp-002", "config_diff": '{"thresholds": {"sell": 35}}',
         "decision": "rejected", "metrics": '{"sharpe": 1.0}'},
    ]
    summary = build_context_summary(baseline_metrics, baseline_config, recent_experiments)
    assert "sharpe" in summary.lower()
    assert "1.1" in summary
    assert "exp-001" in summary
    assert "rejected" in summary.lower()
    assert isinstance(summary, str)

def test_empty_experiments():
    summary = build_context_summary(
        {"sharpe": 1.0}, {"weights": {}, "thresholds": {}, "filters": {}}, []
    )
    assert "no experiments" in summary.lower() or "baseline" in summary.lower()

def test_summary_not_too_long():
    experiments = [
        {"experiment_id": f"exp-{i:03d}", "config_diff": '{}',
         "decision": "rejected", "metrics": '{"sharpe": 0.5}'}
        for i in range(20)
    ]
    summary = build_context_summary({"sharpe": 1.0}, {"weights": {}, "thresholds": {}, "filters": {}}, experiments)
    # Should be bounded — not dump all 20
    assert len(summary) < 5000
