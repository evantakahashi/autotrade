# tests/test_auditor.py
from src.research.auditor import evaluate_gates
from src.research.results import BacktestResult, WindowResult

def _make_result(sharpe_values, max_dd_values=None, turnover_values=None,
                 spy_returns=None, version="0.1"):
    windows = []
    for i, s in enumerate(sharpe_values):
        metrics = {
            "sharpe": s,
            "max_drawdown": max_dd_values[i] if max_dd_values else 0.05,
            "monthly_turnover": turnover_values[i] if turnover_values else 0.1,
            "cagr": s * 0.05,
            "hit_rate": 0.55,
        }
        if spy_returns:
            metrics["spy_return"] = spy_returns[i]
        windows.append(WindowResult(i, "", "", "", "", metrics, {}))
    agg = {"sharpe": sum(sharpe_values) / len(sharpe_values),
           "max_drawdown": max(max_dd_values) if max_dd_values else 0.05,
           "monthly_turnover": sum(turnover_values) / len(turnover_values) if turnover_values else 0.1}
    return BacktestResult(version, windows, agg, {})

def test_all_gates_pass():
    baseline = _make_result([0.8, 0.9, 1.0, 0.7])
    experiment = _make_result([1.2, 1.3, 1.1, 1.4], version="0.2")
    verdict = evaluate_gates(baseline, experiment)
    assert verdict["overall"] == "pass"
    assert all(g["passed"] for g in verdict["gates"])

def test_sharpe_gate_fails():
    baseline = _make_result([1.2, 1.3, 1.1, 1.4])
    experiment = _make_result([0.8, 0.9, 0.7, 0.6], version="0.2")
    verdict = evaluate_gates(baseline, experiment)
    assert verdict["overall"] == "fail"
    sharpe_gate = next(g for g in verdict["gates"] if g["name"] == "sharpe")
    assert not sharpe_gate["passed"]

def test_walkforward_gate_fails():
    baseline = _make_result([1.0, 1.0, 1.0, 1.0])
    # Experiment only wins 1 of 4 windows
    experiment = _make_result([1.1, 0.5, 0.6, 0.4], version="0.2")
    verdict = evaluate_gates(baseline, experiment)
    wf_gate = next(g for g in verdict["gates"] if g["name"] == "walk_forward")
    assert not wf_gate["passed"]

def test_drawdown_gate_fails():
    baseline = _make_result([1.0, 1.0, 1.0, 1.0], max_dd_values=[0.05, 0.05, 0.05, 0.05])
    experiment = _make_result([1.2, 1.2, 1.2, 1.2], max_dd_values=[0.20, 0.20, 0.20, 0.20], version="0.2")
    verdict = evaluate_gates(baseline, experiment)
    dd_gate = next(g for g in verdict["gates"] if g["name"] == "drawdown")
    assert not dd_gate["passed"]

def test_turnover_gate_fails():
    baseline = _make_result([1.0]*4, turnover_values=[0.1]*4)
    experiment = _make_result([1.2]*4, turnover_values=[0.5]*4, version="0.2")
    verdict = evaluate_gates(baseline, experiment)
    to_gate = next(g for g in verdict["gates"] if g["name"] == "turnover")
    assert not to_gate["passed"]

def test_regime_gate():
    # Need spy_return to classify regimes
    baseline = _make_result([1.0, 1.0, 1.0, 1.0])
    # Experiment wins in up markets but loses in down
    experiment = _make_result([1.5, 1.5, 0.5, 0.5], version="0.2")
    # Manually set spy returns: first 2 up, last 2 down
    for i, w in enumerate(baseline.window_results):
        w.metrics["spy_return"] = 0.05 if i < 2 else -0.05
    for i, w in enumerate(experiment.window_results):
        w.metrics["spy_return"] = 0.05 if i < 2 else -0.05
    verdict = evaluate_gates(baseline, experiment)
    regime_gate = next(g for g in verdict["gates"] if g["name"] == "regime_diversity")
    assert not regime_gate["passed"]
