# M3: Autoresearch Loop Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a long-running autonomous loop that proposes strategy experiments via LLM, backtests them, and promotes/rejects based on validation gates.

**Architecture:** ExperimentManager tracks experiments in files + DuckDB. Proposer uses Anthropic SDK to generate hypotheses from structured context. Auditor runs M2 Backtester on baseline + experiment, applies validation gates. Promoter auto-rejects gate failures, uses LLM for promotion narratives. Loop orchestrates with cooldown and rejection limits.

**Tech Stack:** Python 3.12+, anthropic SDK, existing M1/M2 modules

---

### Task 1: Add anthropic SDK dependency + experiment DB methods

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/data/db.py`
- Modify: `.env.example`
- Create: `tests/test_db_experiments.py`

**Step 1: Write failing tests for experiment DB methods**

```python
# tests/test_db_experiments.py
import json
from datetime import datetime
from src.data.db import Storage

def test_store_and_get_experiment(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    db.store_experiment(
        experiment_id="exp-001",
        parent_version="0.1",
        config_diff={"weights": {"trend": 0.40}},
        hypothesis="Increase trend weight",
    )
    experiments = db.get_experiments()
    assert len(experiments) == 1
    assert experiments[0]["experiment_id"] == "exp-001"

def test_update_experiment_decision(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    db.store_experiment("exp-001", "0.1", {}, "test")
    db.update_experiment_decision(
        "exp-001", decision="rejected",
        metrics={"sharpe": 0.8, "cagr": 0.05}
    )
    exp = db.get_experiment("exp-001")
    assert exp["decision"] == "rejected"

def test_get_recent_experiments(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    for i in range(5):
        db.store_experiment(f"exp-{i:03d}", "0.1", {}, f"hypothesis {i}")
    recent = db.get_recent_experiments(limit=3)
    assert len(recent) == 3

def test_store_strategy_version(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    db.store_strategy_version(
        version="0.2", config_hash="abc123",
        metrics={"sharpe": 1.2}
    )
    versions = db.get_strategy_versions()
    assert len(versions) == 1
    assert versions[0]["version"] == "0.2"

def test_get_baseline_version(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    db.store_strategy_version("0.1", "hash1", {"sharpe": 1.0})
    db.store_strategy_version("0.2", "hash2", {"sharpe": 1.2})
    latest = db.get_latest_strategy_version()
    assert latest["version"] == "0.2"
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_db_experiments.py -v`

**Step 3: Add anthropic to pyproject.toml**

Add `"anthropic>=0.40.0"` to the dependencies list in `pyproject.toml`.

**Step 4: Update .env.example**

Add `ANTHROPIC_API_KEY=your_key_here` line.

**Step 5: Add experiment methods to Storage**

Add these methods to the existing `Storage` class in `src/data/db.py`:

```python
def store_experiment(self, experiment_id: str, parent_version: str,
                     config_diff: dict, hypothesis: str):
    self.conn.execute(
        "INSERT OR REPLACE INTO experiments VALUES (?, ?, ?, ?, ?, ?)",
        [experiment_id, parent_version, json.dumps(config_diff),
         None, None, datetime.now()]
    )

def update_experiment_decision(self, experiment_id: str, decision: str, metrics: dict):
    self.conn.execute(
        "UPDATE experiments SET decision = ?, metrics = ? WHERE experiment_id = ?",
        [decision, json.dumps(metrics), experiment_id]
    )

def get_experiment(self, experiment_id: str) -> dict | None:
    df = self.conn.execute(
        "SELECT * FROM experiments WHERE experiment_id = ?", [experiment_id]
    ).fetchdf()
    if df.empty:
        return None
    return df.to_dict("records")[0]

def get_experiments(self) -> list[dict]:
    return self.conn.execute(
        "SELECT * FROM experiments ORDER BY created_at DESC"
    ).fetchdf().to_dict("records")

def get_recent_experiments(self, limit: int = 10) -> list[dict]:
    return self.conn.execute(
        "SELECT * FROM experiments ORDER BY created_at DESC LIMIT ?", [limit]
    ).fetchdf().to_dict("records")

def store_strategy_version(self, version: str, config_hash: str, metrics: dict):
    self.conn.execute(
        "INSERT OR REPLACE INTO strategy_versions VALUES (?, ?, ?, ?)",
        [version, config_hash, datetime.now(), json.dumps(metrics)]
    )

def get_strategy_versions(self) -> list[dict]:
    return self.conn.execute(
        "SELECT * FROM strategy_versions ORDER BY promoted_date DESC"
    ).fetchdf().to_dict("records")

def get_latest_strategy_version(self) -> dict | None:
    df = self.conn.execute(
        "SELECT * FROM strategy_versions ORDER BY promoted_date DESC LIMIT 1"
    ).fetchdf()
    if df.empty:
        return None
    return df.to_dict("records")[0]
```

**Step 6: Install new deps, run tests**

```bash
pip install -e ".[dev]"
pytest tests/test_db_experiments.py -v
```
Expected: PASS

**Step 7: Commit**

```bash
git add pyproject.toml .env.example src/data/db.py tests/test_db_experiments.py
git commit -m "add experiment DB methods and anthropic SDK dep"
```

---

### Task 2: Schema Validator

**Files:**
- Create: `src/research/schema.py`
- Create: `tests/test_schema.py`

**Step 1: Write failing tests**

```python
# tests/test_schema.py
import pytest
from src.research.schema import validate_config_diff, apply_diff, BOUNDS

def test_valid_weight_change():
    baseline = {"weights": {"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                            "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
                "thresholds": {"buy": 70, "sell": 40}, "filters": {}}
    diff = {"weights": {"trend": 0.40, "fundamentals": 0.15}}
    errors = validate_config_diff(baseline, diff)
    assert len(errors) == 0

def test_weight_exceeds_max():
    baseline = {"weights": {"trend": 0.35}, "thresholds": {"buy": 70, "sell": 40}, "filters": {}}
    diff = {"weights": {"trend": 0.60}}  # max 0.5
    errors = validate_config_diff(baseline, diff)
    assert any("trend" in e for e in errors)

def test_weights_dont_sum_to_one():
    baseline = {"weights": {"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                            "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
                "thresholds": {"buy": 70, "sell": 40}, "filters": {}}
    diff = {"weights": {"trend": 0.50}}  # now sums to 1.15
    errors = validate_config_diff(baseline, diff)
    assert any("sum" in e.lower() for e in errors)

def test_threshold_out_of_range():
    baseline = {"weights": {"trend": 1.0}, "thresholds": {"buy": 70, "sell": 40}, "filters": {}}
    diff = {"thresholds": {"buy": 95}}  # max 90
    errors = validate_config_diff(baseline, diff)
    assert len(errors) > 0

def test_buy_below_sell():
    baseline = {"weights": {"trend": 1.0}, "thresholds": {"buy": 70, "sell": 40}, "filters": {}}
    diff = {"thresholds": {"buy": 35}}  # below sell
    errors = validate_config_diff(baseline, diff)
    assert any("buy" in e.lower() and "sell" in e.lower() for e in errors)

def test_apply_diff():
    baseline = {"weights": {"trend": 0.35, "volatility": 0.15},
                "thresholds": {"buy": 70, "sell": 40}, "filters": {}}
    diff = {"weights": {"trend": 0.40}, "thresholds": {"sell": 35}}
    merged = apply_diff(baseline, diff)
    assert merged["weights"]["trend"] == 0.40
    assert merged["weights"]["volatility"] == 0.15  # unchanged
    assert merged["thresholds"]["sell"] == 35
    assert merged["thresholds"]["buy"] == 70  # unchanged
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_schema.py -v`

**Step 3: Implement**

```python
# src/research/schema.py
import copy

BOUNDS = {
    "weights": {"min": 0.0, "max": 0.5},
    "thresholds": {
        "buy": {"min": 50, "max": 90},
        "sell": {"min": 20, "max": 60},
    },
    "filters": {
        "min_price": {"min": 1.0, "max": 50.0},
        "min_avg_volume": {"min": 100_000, "max": 5_000_000},
        "max_annual_volatility": {"min": 20, "max": 200},
    },
}

def validate_config_diff(baseline: dict, diff: dict) -> list[str]:
    """Validate a proposed config diff against schema bounds. Returns list of error strings."""
    errors = []
    merged = apply_diff(baseline, diff)

    # Validate weights
    if "weights" in merged:
        for name, val in merged["weights"].items():
            if val < BOUNDS["weights"]["min"] or val > BOUNDS["weights"]["max"]:
                errors.append(f"Weight '{name}' = {val} outside bounds [{BOUNDS['weights']['min']}, {BOUNDS['weights']['max']}]")
        total = sum(merged["weights"].values())
        if abs(total - 1.0) > 0.01:
            errors.append(f"Weights sum to {total:.3f}, must sum to 1.0")

    # Validate thresholds
    if "thresholds" in merged:
        for name, val in merged["thresholds"].items():
            if name in BOUNDS["thresholds"]:
                bounds = BOUNDS["thresholds"][name]
                if val < bounds["min"] or val > bounds["max"]:
                    errors.append(f"Threshold '{name}' = {val} outside bounds [{bounds['min']}, {bounds['max']}]")
        buy = merged["thresholds"].get("buy", 70)
        sell = merged["thresholds"].get("sell", 40)
        if buy <= sell:
            errors.append(f"Buy threshold ({buy}) must be above sell threshold ({sell})")

    # Validate filters
    if "filters" in merged:
        for name, val in merged["filters"].items():
            if name in BOUNDS["filters"]:
                bounds = BOUNDS["filters"][name]
                if val < bounds["min"] or val > bounds["max"]:
                    errors.append(f"Filter '{name}' = {val} outside bounds [{bounds['min']}, {bounds['max']}]")

    return errors

def apply_diff(baseline: dict, diff: dict) -> dict:
    """Deep merge diff into baseline. Returns new dict."""
    merged = copy.deepcopy(baseline)
    for key, val in diff.items():
        if isinstance(val, dict) and key in merged and isinstance(merged[key], dict):
            merged[key].update(val)
        else:
            merged[key] = val
    return merged
```

**Step 4: Run tests — verify pass**

Run: `pytest tests/test_schema.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/research/schema.py tests/test_schema.py
git commit -m "add schema validator for experiment configs"
```

---

### Task 3: Context Builder

**Files:**
- Create: `src/research/context.py`
- Create: `tests/test_context.py`

**Step 1: Write failing tests**

```python
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
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_context.py -v`

**Step 3: Implement**

```python
# src/research/context.py
import json

def build_context_summary(
    baseline_metrics: dict,
    baseline_config: dict,
    recent_experiments: list[dict],
    max_experiments: int = 10,
) -> str:
    """Build a structured context summary for the LLM proposer."""
    lines = []

    # Baseline performance
    lines.append("## Current Baseline Strategy")
    lines.append(f"- Sharpe: {baseline_metrics.get('sharpe', 'N/A')}")
    lines.append(f"- CAGR: {baseline_metrics.get('cagr', 'N/A')}")
    lines.append(f"- Max Drawdown: {baseline_metrics.get('max_drawdown', 'N/A')}")
    lines.append(f"- Hit Rate: {baseline_metrics.get('hit_rate', 'N/A')}")

    # Baseline config
    lines.append("\n## Baseline Config")
    weights = baseline_config.get("weights", {})
    if weights:
        lines.append("Weights: " + ", ".join(f"{k}={v}" for k, v in weights.items()))
    thresholds = baseline_config.get("thresholds", {})
    if thresholds:
        lines.append("Thresholds: " + ", ".join(f"{k}={v}" for k, v in thresholds.items()))
    filters = baseline_config.get("filters", {})
    if filters:
        lines.append("Filters: " + ", ".join(f"{k}={v}" for k, v in filters.items()))

    # Recent experiments
    experiments = recent_experiments[:max_experiments]
    if not experiments:
        lines.append("\n## Recent Experiments\nNo experiments run yet.")
    else:
        lines.append(f"\n## Recent Experiments ({len(experiments)} most recent)")
        rejected_changes = []
        promoted_changes = []
        for exp in experiments:
            eid = exp.get("experiment_id", "?")
            decision = exp.get("decision", "pending")
            diff_raw = exp.get("config_diff", "{}")
            diff = json.loads(diff_raw) if isinstance(diff_raw, str) else diff_raw
            metrics_raw = exp.get("metrics", "{}")
            metrics = json.loads(metrics_raw) if isinstance(metrics_raw, str) else (metrics_raw or {})
            sharpe = metrics.get("sharpe", "?")
            diff_summary = _summarize_diff(diff)
            line = f"- {eid}: {diff_summary} → {decision} (Sharpe: {sharpe})"
            lines.append(line)
            if decision == "rejected":
                rejected_changes.append(diff_summary)
            elif decision == "promoted":
                promoted_changes.append(diff_summary)

        # Synthesize patterns
        if rejected_changes:
            lines.append(f"\nRejected approaches: {'; '.join(rejected_changes[:5])}")
        if promoted_changes:
            lines.append(f"Successful approaches: {'; '.join(promoted_changes[:5])}")

    # Suggestions
    lines.append("\n## Unexplored Areas")
    explored_keys = set()
    for exp in experiments:
        diff_raw = exp.get("config_diff", "{}")
        diff = json.loads(diff_raw) if isinstance(diff_raw, str) else diff_raw
        for section in diff.values():
            if isinstance(section, dict):
                explored_keys.update(section.keys())
    all_keys = set(weights.keys()) | set(thresholds.keys()) | set(filters.keys())
    unexplored = all_keys - explored_keys
    if unexplored:
        lines.append(f"Not yet tested: {', '.join(sorted(unexplored))}")
    else:
        lines.append("All parameters have been tested at least once. Try combinations or larger changes.")

    return "\n".join(lines)

def _summarize_diff(diff: dict) -> str:
    parts = []
    for section, changes in diff.items():
        if isinstance(changes, dict):
            for k, v in changes.items():
                parts.append(f"{k}→{v}")
        else:
            parts.append(f"{section}→{changes}")
    return ", ".join(parts) if parts else "no changes"
```

**Step 4: Run tests — verify pass**

Run: `pytest tests/test_context.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/research/context.py tests/test_context.py
git commit -m "add context builder for LLM proposer"
```

---

### Task 4: ExperimentManager

**Files:**
- Create: `src/research/experiment.py`
- Create: `tests/test_experiment.py`

**Step 1: Write failing tests**

```python
# tests/test_experiment.py
import json
from pathlib import Path
from src.research.experiment import ExperimentManager
from src.data.db import Storage

def test_create_experiment(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    mgr = ExperimentManager(db, experiments_dir=str(tmp_path / "experiments"))
    exp = mgr.create(
        parent_version="0.1",
        config_diff={"weights": {"trend": 0.40, "fundamentals": 0.15}},
        hypothesis="Increase trend weight to capture stronger momentum",
    )
    assert exp["experiment_id"] == "exp-001"
    assert (tmp_path / "experiments" / "exp-001-increase-trend-weight").exists()
    assert (tmp_path / "experiments" / "exp-001-increase-trend-weight" / "config.yaml").exists()
    assert (tmp_path / "experiments" / "exp-001-increase-trend-weight" / "hypothesis.md").exists()

def test_sequential_ids(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    mgr = ExperimentManager(db, experiments_dir=str(tmp_path / "experiments"))
    e1 = mgr.create("0.1", {"weights": {"trend": 0.40}}, "first")
    e2 = mgr.create("0.1", {"weights": {"trend": 0.45}}, "second")
    assert e1["experiment_id"] == "exp-001"
    assert e2["experiment_id"] == "exp-002"

def test_record_decision(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    mgr = ExperimentManager(db, experiments_dir=str(tmp_path / "experiments"))
    exp = mgr.create("0.1", {"weights": {"trend": 0.40}}, "test")
    mgr.record_decision(
        exp["experiment_id"], exp["dir_name"],
        decision="rejected",
        metrics={"sharpe": 0.8},
        reasoning="Sharpe decreased",
    )
    # Check DB
    stored = db.get_experiment(exp["experiment_id"])
    assert stored["decision"] == "rejected"
    # Check file
    decision_file = tmp_path / "experiments" / exp["dir_name"] / "decision.md"
    assert decision_file.exists()
    assert "rejected" in decision_file.read_text().lower()

def test_get_next_id(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    mgr = ExperimentManager(db, experiments_dir=str(tmp_path / "experiments"))
    assert mgr._next_id() == "exp-001"
    mgr.create("0.1", {}, "test")
    assert mgr._next_id() == "exp-002"
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_experiment.py -v`

**Step 3: Implement**

```python
# src/research/experiment.py
import json
import re
import yaml
from pathlib import Path
from src.data.db import Storage

class ExperimentManager:
    def __init__(self, db: Storage, experiments_dir: str = "experiments"):
        self.db = db
        self.experiments_dir = Path(experiments_dir)
        self.experiments_dir.mkdir(exist_ok=True)

    def create(self, parent_version: str, config_diff: dict, hypothesis: str) -> dict:
        exp_id = self._next_id()
        # Create slug from hypothesis (first few words)
        slug = re.sub(r"[^a-z0-9]+", "-", hypothesis.lower().strip())[:40].strip("-")
        dir_name = f"{exp_id}-{slug}"
        exp_dir = self.experiments_dir / dir_name
        exp_dir.mkdir(parents=True, exist_ok=True)

        # Write config.yaml
        (exp_dir / "config.yaml").write_text(yaml.dump(config_diff, default_flow_style=False))

        # Write hypothesis.md
        (exp_dir / "hypothesis.md").write_text(f"# {exp_id}: {hypothesis}\n\n"
                                                 f"Parent version: {parent_version}\n\n"
                                                 f"Config diff:\n```yaml\n{yaml.dump(config_diff)}\n```\n")

        # Store in DB
        self.db.store_experiment(exp_id, parent_version, config_diff, hypothesis)

        return {
            "experiment_id": exp_id,
            "dir_name": dir_name,
            "parent_version": parent_version,
            "config_diff": config_diff,
            "hypothesis": hypothesis,
        }

    def record_decision(self, experiment_id: str, dir_name: str,
                        decision: str, metrics: dict, reasoning: str):
        # Update DB
        self.db.update_experiment_decision(experiment_id, decision, metrics)

        # Write decision.md
        exp_dir = self.experiments_dir / dir_name
        exp_dir.mkdir(exist_ok=True)
        (exp_dir / "decision.md").write_text(
            f"# Decision: {decision.upper()}\n\n"
            f"## Metrics\n```json\n{json.dumps(metrics, indent=2)}\n```\n\n"
            f"## Reasoning\n{reasoning}\n"
        )

        # Write results.json
        (exp_dir / "results.json").write_text(json.dumps({
            "experiment_id": experiment_id,
            "decision": decision,
            "metrics": metrics,
        }, indent=2))

    def _next_id(self) -> str:
        experiments = self.db.get_experiments()
        if not experiments:
            return "exp-001"
        ids = [e["experiment_id"] for e in experiments]
        nums = [int(re.search(r"\d+", eid).group()) for eid in ids if re.search(r"\d+", eid)]
        next_num = max(nums) + 1 if nums else 1
        return f"exp-{next_num:03d}"
```

**Step 4: Run tests — verify pass**

Run: `pytest tests/test_experiment.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/research/experiment.py tests/test_experiment.py
git commit -m "add ExperimentManager with file and DB tracking"
```

---

### Task 5: Auditor (Validation Gates)

**Files:**
- Create: `src/research/auditor.py`
- Create: `tests/test_auditor.py`

**Step 1: Write failing tests**

```python
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
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_auditor.py -v`

**Step 3: Implement**

```python
# src/research/auditor.py
from src.research.results import BacktestResult

def evaluate_gates(
    baseline: BacktestResult,
    experiment: BacktestResult,
    max_drawdown_ratio: float = 1.5,
    max_turnover_ratio: float = 2.0,
    min_window_win_rate: float = 0.75,
) -> dict:
    """Evaluate all validation gates. Returns verdict dict."""
    b_windows = baseline.window_results
    e_windows = experiment.window_results
    n = min(len(b_windows), len(e_windows))

    gates = []

    # Gate 1: Sharpe improvement on aggregate
    b_sharpe = baseline.aggregate_metrics.get("sharpe", 0)
    e_sharpe = experiment.aggregate_metrics.get("sharpe", 0)
    gates.append({
        "name": "sharpe",
        "passed": e_sharpe > b_sharpe,
        "detail": f"baseline={b_sharpe:.3f}, experiment={e_sharpe:.3f}",
    })

    # Gate 2: Walk-forward consistency
    windows_won = 0
    for i in range(n):
        if e_windows[i].metrics.get("sharpe", 0) > b_windows[i].metrics.get("sharpe", 0):
            windows_won += 1
    win_rate = windows_won / n if n > 0 else 0
    gates.append({
        "name": "walk_forward",
        "passed": win_rate >= min_window_win_rate,
        "detail": f"won {windows_won}/{n} windows ({win_rate:.0%}), need {min_window_win_rate:.0%}",
    })

    # Gate 3: Drawdown
    b_max_dd = max((w.metrics.get("max_drawdown", 0) for w in b_windows), default=0)
    e_max_dd = max((w.metrics.get("max_drawdown", 0) for w in e_windows), default=0)
    dd_ok = e_max_dd <= b_max_dd * max_drawdown_ratio if b_max_dd > 0 else True
    gates.append({
        "name": "drawdown",
        "passed": dd_ok,
        "detail": f"baseline_max={b_max_dd:.3f}, experiment_max={e_max_dd:.3f}, "
                  f"ratio={e_max_dd/b_max_dd:.2f}x" if b_max_dd > 0 else "no baseline drawdown",
    })

    # Gate 4: Turnover
    b_turnover = baseline.aggregate_metrics.get("monthly_turnover", 0)
    e_turnover = experiment.aggregate_metrics.get("monthly_turnover", 0)
    to_ok = e_turnover <= b_turnover * max_turnover_ratio if b_turnover > 0 else True
    gates.append({
        "name": "turnover",
        "passed": to_ok,
        "detail": f"baseline={b_turnover:.3f}, experiment={e_turnover:.3f}",
    })

    # Gate 5: Regime diversity
    up_wins = 0
    up_total = 0
    down_wins = 0
    down_total = 0
    for i in range(n):
        spy_ret = e_windows[i].metrics.get("spy_return")
        if spy_ret is None:
            # Can't classify regime — skip gate
            continue
        e_sharpe_w = e_windows[i].metrics.get("sharpe", 0)
        b_sharpe_w = b_windows[i].metrics.get("sharpe", 0)
        if spy_ret >= 0:
            up_total += 1
            if e_sharpe_w > b_sharpe_w:
                up_wins += 1
        else:
            down_total += 1
            if e_sharpe_w > b_sharpe_w:
                down_wins += 1

    if up_total > 0 and down_total > 0:
        regime_ok = up_wins > 0 and down_wins > 0
        gates.append({
            "name": "regime_diversity",
            "passed": regime_ok,
            "detail": f"up markets: won {up_wins}/{up_total}, down markets: won {down_wins}/{down_total}",
        })
    else:
        gates.append({
            "name": "regime_diversity",
            "passed": True,
            "detail": "insufficient regime data — gate skipped",
        })

    # Gate 6: Paper trading (stubbed — always passes in M3)
    gates.append({
        "name": "paper_trading",
        "passed": True,
        "detail": "stubbed — paper trading gate not enforced until M5",
    })

    overall = "pass" if all(g["passed"] for g in gates) else "fail"
    failed_gates = [g["name"] for g in gates if not g["passed"]]

    return {
        "overall": overall,
        "gates": gates,
        "failed_gates": failed_gates,
    }
```

**Step 4: Run tests — verify pass**

Run: `pytest tests/test_auditor.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/research/auditor.py tests/test_auditor.py
git commit -m "add auditor with 6 validation gates"
```

---

### Task 6: Proposer (LLM-powered)

**Files:**
- Create: `src/research/proposer.py`
- Create: `tests/test_proposer.py`

**Step 1: Write failing tests**

The proposer calls the Anthropic SDK, so tests mock the API call.

```python
# tests/test_proposer.py
import json
from unittest.mock import MagicMock, patch
from src.research.proposer import Proposer, parse_proposal

def test_parse_proposal_valid_json():
    llm_output = """Based on the analysis, I propose increasing the trend weight.

```json
{
  "config_diff": {"weights": {"trend": 0.40, "fundamentals": 0.15}},
  "hypothesis": "Increase trend weight to better capture momentum signals"
}
```"""
    result = parse_proposal(llm_output)
    assert result["config_diff"]["weights"]["trend"] == 0.40
    assert "hypothesis" in result

def test_parse_proposal_no_json():
    result = parse_proposal("I think we should try something different")
    assert result is None

def test_proposer_returns_valid_proposal():
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = """```json
{
  "config_diff": {"weights": {"trend": 0.40, "fundamentals": 0.15}},
  "hypothesis": "Increase trend weight"
}
```"""
    with patch("src.research.proposer.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = mock_response

        proposer = Proposer()
        result = proposer.propose("test context summary")
        assert result is not None
        assert "config_diff" in result
        assert "hypothesis" in result

def test_proposer_retries_on_invalid():
    # First response is invalid, second is valid
    invalid_response = MagicMock()
    invalid_response.content = [MagicMock()]
    invalid_response.content[0].text = "I'm not sure what to suggest"

    valid_response = MagicMock()
    valid_response.content = [MagicMock()]
    valid_response.content[0].text = '```json\n{"config_diff": {"weights": {"trend": 0.40, "fundamentals": 0.15}}, "hypothesis": "test"}\n```'

    with patch("src.research.proposer.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = [invalid_response, valid_response]

        proposer = Proposer(max_retries=2)
        result = proposer.propose("test context")
        assert result is not None
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_proposer.py -v`

**Step 3: Implement**

```python
# src/research/proposer.py
import json
import re
import anthropic

SYSTEM_PROMPT = """You are a quantitative signal researcher for a stock ranking system.

Your job: propose ONE small, testable change to the strategy config.

Rules:
- Propose exactly one change (a weight adjustment, threshold change, or filter modification)
- Changes must be small and incremental (e.g., shift a weight by 0.05, not 0.30)
- Weights must sum to 1.0 after your change
- Do NOT propose changes that were recently rejected (see experiment history)
- Explain your hypothesis in one sentence

You MUST respond with a JSON block in this exact format:
```json
{
  "config_diff": {"weights": {"trend": 0.40, "fundamentals": 0.15}},
  "hypothesis": "One sentence explaining why this change should improve performance"
}
```

The config_diff should only include the keys you want to change. Unchanged values will be kept from baseline."""

class Proposer:
    def __init__(self, model: str = "claude-sonnet-4-20250514", max_retries: int = 3):
        self.client = anthropic.Anthropic()
        self.model = model
        self.max_retries = max_retries

    def propose(self, context_summary: str) -> dict | None:
        for attempt in range(self.max_retries):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": context_summary}],
            )
            text = response.content[0].text
            result = parse_proposal(text)
            if result is not None:
                return result
        return None

def parse_proposal(text: str) -> dict | None:
    """Extract JSON proposal from LLM response."""
    # Try to find ```json ... ``` block
    match = re.search(r"```json\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if "config_diff" in data and "hypothesis" in data:
                return data
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON object
    match = re.search(r"\{[^{}]*\"config_diff\"[^{}]*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if "config_diff" in data and "hypothesis" in data:
                return data
        except json.JSONDecodeError:
            pass

    return None
```

**Step 4: Run tests — verify pass**

Run: `pytest tests/test_proposer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/research/proposer.py tests/test_proposer.py
git commit -m "add LLM-powered Proposer for experiment generation"
```

---

### Task 7: Promoter (LLM-assisted decisions)

**Files:**
- Create: `src/research/promoter.py`
- Create: `tests/test_promoter.py`

**Step 1: Write failing tests**

```python
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
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = "This experiment improved Sharpe from 1.0 to 1.2 across all windows. Promoting."

    with patch("src.research.promoter.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = mock_response

        promoter = Promoter()
        decision = promoter.decide(_passing_verdict(), "exp-001", {"weights": {"trend": 0.40}})
        assert decision["decision"] == "promoted"
        assert decision["reasoning"] != ""

def test_reject_does_not_call_llm():
    with patch("src.research.promoter.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        promoter = Promoter()
        promoter.decide(_failing_verdict(), "exp-001", {})
        # LLM should NOT be called for rejections
        mock_client.messages.create.assert_not_called()
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_promoter.py -v`

**Step 3: Implement**

```python
# src/research/promoter.py
import anthropic

DECISION_PROMPT = """You are a strategy promoter for a quant autoresearch system.

An experiment has passed ALL validation gates. Review the results and write a brief promotion rationale.

Experiment: {experiment_id}
Config changes: {config_diff}

Gate results:
{gate_details}

Write 2-3 sentences explaining why this change is being promoted. Be specific about the metrics."""

class Promoter:
    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model

    def decide(self, verdict: dict, experiment_id: str, config_diff: dict) -> dict:
        # Auto-reject if any gate failed
        if verdict["overall"] == "fail":
            failed = verdict["failed_gates"]
            gate_details = "\n".join(
                f"  {g['name']}: {'PASS' if g['passed'] else 'FAIL'} — {g['detail']}"
                for g in verdict["gates"]
            )
            return {
                "decision": "rejected",
                "reasoning": f"Auto-rejected: failed gates: {', '.join(failed)}.\n{gate_details}",
            }

        # All gates pass — call LLM for promotion narrative
        gate_details = "\n".join(
            f"  {g['name']}: PASS — {g['detail']}"
            for g in verdict["gates"]
        )
        prompt = DECISION_PROMPT.format(
            experiment_id=experiment_id,
            config_diff=config_diff,
            gate_details=gate_details,
        )

        try:
            client = anthropic.Anthropic()
            response = client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            reasoning = response.content[0].text
        except Exception as e:
            reasoning = f"All gates passed. Auto-promoting. (LLM unavailable: {e})"

        return {
            "decision": "promoted",
            "reasoning": reasoning,
        }
```

**Step 4: Run tests — verify pass**

Run: `pytest tests/test_promoter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/research/promoter.py tests/test_promoter.py
git commit -m "add Promoter with auto-reject and LLM promotion narratives"
```

---

### Task 8: Strategy Promotion Logic

**Files:**
- Create: `src/strategy/registry.py`
- Create: `tests/test_registry.py`

**Step 1: Write failing tests**

```python
# tests/test_registry.py
import yaml
from pathlib import Path
from src.strategy.registry import StrategyRegistry
from src.data.db import Storage

def test_promote_creates_new_version(tmp_path):
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir()
    # Create baseline
    baseline = {
        "version": "0.1", "name": "baseline",
        "weights": {"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                     "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
        "thresholds": {"buy": 70, "hold_min": 40, "sell": 40},
        "filters": {}, "backtest": {},
    }
    (strategies_dir / "v0.1.yaml").write_text(yaml.dump(baseline))

    db = Storage(str(tmp_path / "test.duckdb"))
    registry = StrategyRegistry(db, str(strategies_dir))

    new_version = registry.promote(
        parent_version="0.1",
        config_diff={"weights": {"trend": 0.40, "fundamentals": 0.15}},
        metrics={"sharpe": 1.3},
    )
    assert new_version == "0.2"
    assert (strategies_dir / "v0.2.yaml").exists()

    # Verify merged config
    new_config = yaml.safe_load((strategies_dir / "v0.2.yaml").read_text())
    assert new_config["weights"]["trend"] == 0.40
    assert new_config["weights"]["relative_strength"] == 0.10  # unchanged
    assert new_config["version"] == "0.2"

def test_get_current_version(tmp_path):
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir()
    config = {"version": "0.1", "name": "baseline", "weights": {"trend": 1.0},
              "thresholds": {"buy": 70, "sell": 40}, "filters": {}, "backtest": {}}
    (strategies_dir / "v0.1.yaml").write_text(yaml.dump(config))

    db = Storage(str(tmp_path / "test.duckdb"))
    registry = StrategyRegistry(db, str(strategies_dir))
    assert registry.get_current_version() == "0.1"

def test_sequential_version_bumps(tmp_path):
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir()
    config = {"version": "0.1", "name": "baseline", "weights": {"trend": 0.5, "volatility": 0.5},
              "thresholds": {"buy": 70, "sell": 40}, "filters": {}, "backtest": {}}
    (strategies_dir / "v0.1.yaml").write_text(yaml.dump(config))

    db = Storage(str(tmp_path / "test.duckdb"))
    registry = StrategyRegistry(db, str(strategies_dir))
    v1 = registry.promote("0.1", {"weights": {"trend": 0.45, "volatility": 0.55}}, {})
    v2 = registry.promote(v1, {"weights": {"trend": 0.40, "volatility": 0.60}}, {})
    assert v1 == "0.2"
    assert v2 == "0.3"
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_registry.py -v`

**Step 3: Implement**

```python
# src/strategy/registry.py
import hashlib
import yaml
from pathlib import Path
from src.data.db import Storage
from src.research.schema import apply_diff

class StrategyRegistry:
    def __init__(self, db: Storage, strategies_dir: str = "strategies"):
        self.db = db
        self.strategies_dir = Path(strategies_dir)

    def promote(self, parent_version: str, config_diff: dict, metrics: dict) -> str:
        # Load parent config
        parent_path = self.strategies_dir / f"v{parent_version}.yaml"
        parent_config = yaml.safe_load(parent_path.read_text())

        # Merge diff
        merged = apply_diff(parent_config, config_diff)

        # Bump version
        new_version = self._next_version(parent_version)
        merged["version"] = new_version
        merged["name"] = f"promoted-from-{parent_version}"

        # Write new config
        new_path = self.strategies_dir / f"v{new_version}.yaml"
        new_path.write_text(yaml.dump(merged, default_flow_style=False, sort_keys=False))

        # Record in DB
        config_hash = hashlib.sha256(yaml.dump(merged).encode()).hexdigest()[:12]
        self.db.store_strategy_version(new_version, config_hash, metrics)

        return new_version

    def get_current_version(self) -> str:
        # Check DB for latest promoted version
        latest = self.db.get_latest_strategy_version()
        if latest:
            return latest["version"]
        # Fallback: find highest version file
        versions = sorted(self.strategies_dir.glob("v*.yaml"))
        if versions:
            name = versions[-1].stem  # e.g. "v0.1"
            return name[1:]  # strip "v"
        return "0.1"

    def get_current_config_path(self) -> str:
        version = self.get_current_version()
        return str(self.strategies_dir / f"v{version}.yaml")

    def _next_version(self, parent: str) -> str:
        parts = parent.split(".")
        if len(parts) == 2:
            major, minor = int(parts[0]), int(parts[1])
            return f"{major}.{minor + 1}"
        return f"{parent}.1"
```

**Step 4: Run tests — verify pass**

Run: `pytest tests/test_registry.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/strategy/registry.py tests/test_registry.py
git commit -m "add StrategyRegistry for version promotion"
```

---

### Task 9: Main Loop + CLI

**Files:**
- Create: `src/research/loop.py`
- Create: `research.py`
- Create: `tests/test_loop.py`

**Step 1: Write failing tests**

```python
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
        mock_promoter.decide.return_value = {"decision": "rejected", "reasoning": "test"}
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
        assert result["decision"] in ("rejected", "promoted")

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
        mock_promoter.decide.return_value = {"decision": "rejected", "reasoning": "test"}
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
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_loop.py -v`

**Step 3: Implement loop**

```python
# src/research/loop.py
import time
import logging
import pandas as pd
from src.data.db import Storage
from src.strategy.config import load_strategy
from src.strategy.registry import StrategyRegistry
from src.research.proposer import Proposer
from src.research.promoter import Promoter
from src.research.experiment import ExperimentManager
from src.research.auditor import evaluate_gates
from src.research.backtester import Backtester
from src.research.context import build_context_summary
from src.research.schema import validate_config_diff, apply_diff

logger = logging.getLogger(__name__)

class ResearchLoop:
    def __init__(
        self,
        tickers: list[str],
        bars: dict[str, pd.DataFrame],
        strategies_dir: str = "strategies",
        experiments_dir: str = "experiments",
        db_path: str = "data/trading_agent.duckdb",
        cooldown_seconds: int = 3600,
        max_consecutive_rejections: int = 10,
    ):
        self.tickers = tickers
        self.bars = bars
        self.db = Storage(db_path)
        self.registry = StrategyRegistry(self.db, strategies_dir)
        self.manager = ExperimentManager(self.db, experiments_dir)
        self.proposer = Proposer()
        self.promoter = Promoter()
        self.cooldown_seconds = cooldown_seconds
        self.max_consecutive_rejections = max_consecutive_rejections
        self.consecutive_rejections = 0

    def run(self, max_iterations: int | None = None) -> list[dict]:
        """Run the research loop. Returns list of iteration results."""
        results = []
        iteration = 0
        while True:
            if max_iterations and iteration >= max_iterations:
                break
            if self.consecutive_rejections >= self.max_consecutive_rejections:
                logger.info(f"Pausing: {self.consecutive_rejections} consecutive rejections")
                break

            result = self.run_one_iteration()
            results.append(result)

            if result["decision"] == "rejected":
                self.consecutive_rejections += 1
            else:
                self.consecutive_rejections = 0

            iteration += 1

            if max_iterations is None and iteration < (max_iterations or float("inf")):
                time.sleep(self.cooldown_seconds)

        self.db.close()
        return results

    def run_one_iteration(self) -> dict:
        # Load current baseline
        config_path = self.registry.get_current_config_path()
        baseline_config = load_strategy(config_path)

        # Backtest baseline
        baseline_bt = Backtester(baseline_config)
        baseline_result = baseline_bt.run(self.tickers, self.bars)

        # Build context
        baseline_snapshot = {
            "weights": baseline_config.weights,
            "thresholds": baseline_config.thresholds,
            "filters": baseline_config.filters,
        }
        recent = self.db.get_recent_experiments(limit=10)
        context = build_context_summary(
            baseline_result.aggregate_metrics, baseline_snapshot, recent
        )

        # Propose experiment
        proposal = self.proposer.propose(context)
        if proposal is None:
            return {"experiment_id": None, "decision": "skipped", "reason": "no valid proposal"}

        # Validate
        errors = validate_config_diff(baseline_snapshot, proposal["config_diff"])
        if errors:
            logger.warning(f"Invalid proposal: {errors}")
            return {"experiment_id": None, "decision": "skipped", "reason": f"invalid: {errors}"}

        # Create experiment
        exp = self.manager.create(
            parent_version=baseline_config.version,
            config_diff=proposal["config_diff"],
            hypothesis=proposal["hypothesis"],
        )

        # Build experiment config
        merged_dict = apply_diff(baseline_snapshot, proposal["config_diff"])
        exp_config = load_strategy.__wrapped__(merged_dict) if hasattr(load_strategy, '__wrapped__') else _build_config(
            baseline_config, merged_dict
        )

        # Backtest experiment
        exp_bt = Backtester(exp_config)
        exp_result = exp_bt.run(self.tickers, self.bars)

        # Evaluate gates
        verdict = evaluate_gates(baseline_result, exp_result)

        # Decide
        decision = self.promoter.decide(verdict, exp["experiment_id"], proposal["config_diff"])

        # Promote if needed
        if decision["decision"] == "promoted":
            new_version = self.registry.promote(
                parent_version=baseline_config.version,
                config_diff=proposal["config_diff"],
                metrics=exp_result.aggregate_metrics,
            )
            decision["new_version"] = new_version
            logger.info(f"Promoted {exp['experiment_id']} → v{new_version}")

        # Record
        self.manager.record_decision(
            exp["experiment_id"], exp["dir_name"],
            decision=decision["decision"],
            metrics=exp_result.aggregate_metrics,
            reasoning=decision["reasoning"],
        )

        return {
            "experiment_id": exp["experiment_id"],
            "decision": decision["decision"],
            "metrics": exp_result.aggregate_metrics,
            "hypothesis": proposal["hypothesis"],
        }

def _build_config(baseline_config, merged_dict):
    """Build a StrategyConfig from merged dict, preserving backtest config."""
    from src.strategy.config import StrategyConfig
    return StrategyConfig(
        version=f"{baseline_config.version}-exp",
        name="experiment",
        weights=merged_dict.get("weights", baseline_config.weights),
        thresholds=merged_dict.get("thresholds", baseline_config.thresholds),
        filters=merged_dict.get("filters", baseline_config.filters),
        backtest=baseline_config.backtest,
    )
```

**Step 4: Implement research.py CLI**

```python
#!/usr/bin/env python3
"""Quant Autoresearch Agent — Research Loop CLI."""
import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.data.alpaca import AlpacaProvider
from src.research.loop import ResearchLoop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def main():
    parser = argparse.ArgumentParser(description="Run the autoresearch loop")
    parser.add_argument("tickers", nargs="+", help="Tickers to research")
    parser.add_argument("--days", type=int, default=730, help="Days of history")
    parser.add_argument("--max-iterations", type=int, default=None, help="Max iterations (default: unlimited)")
    parser.add_argument("--cooldown", type=int, default=3600, help="Seconds between iterations")
    parser.add_argument("--max-rejections", type=int, default=10, help="Stop after N consecutive rejections")
    args = parser.parse_args()

    load_dotenv()
    for key in ["ALPACA_API_KEY", "ALPACA_SECRET", "ANTHROPIC_API_KEY"]:
        if not os.environ.get(key):
            print(f"Error: Set {key} in .env")
            sys.exit(1)

    provider = AlpacaProvider()
    tickers = [t.upper() for t in args.tickers]
    all_tickers = tickers + ["SPY"]
    end = datetime.now()
    start = end - timedelta(days=args.days)

    print(f"Fetching {args.days} days of data for {len(tickers)} tickers + SPY...")
    all_bars_df = provider.get_bars(all_tickers, start, end)
    if all_bars_df.empty:
        print("No data returned.")
        sys.exit(1)

    bars = {}
    for ticker in all_tickers:
        mask = all_bars_df["symbol"] == ticker
        if mask.any():
            bars[ticker] = all_bars_df[mask].sort_values("timestamp").reset_index(drop=True)

    print(f"Starting research loop (cooldown={args.cooldown}s, max_rejections={args.max_rejections})...")
    loop = ResearchLoop(
        tickers=tickers, bars=bars,
        cooldown_seconds=args.cooldown,
        max_consecutive_rejections=args.max_rejections,
    )
    results = loop.run(max_iterations=args.max_iterations)

    print(f"\n{'='*60}")
    print(f"  Research Loop Complete — {len(results)} iterations")
    print(f"{'='*60}")
    for r in results:
        status = "✓" if r["decision"] == "promoted" else "✗"
        print(f"  {status} {r.get('experiment_id', '?')}: {r['decision']} — {r.get('hypothesis', '')[:60]}")

if __name__ == "__main__":
    main()
```

**Step 5: Run tests — verify pass**

Run: `pytest tests/test_loop.py -v`
Expected: PASS

**Step 6: Run full suite**

Run: `pytest tests/ -v`

**Step 7: Commit**

```bash
git add src/research/loop.py research.py tests/test_loop.py
git commit -m "add autoresearch loop with CLI entrypoint"
```

---

### Task 10: Integration Test

**Files:**
- Create: `tests/test_research_integration.py`

**Step 1: Write end-to-end test**

```python
# tests/test_research_integration.py
"""End-to-end: mock LLM → propose → backtest → evaluate → reject/promote."""
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
```

**Step 2: Run tests**

Run: `pytest tests/test_research_integration.py -v`
Expected: PASS

**Step 3: Run full suite**

Run: `pytest tests/ -v`

**Step 4: Commit**

```bash
git add tests/test_research_integration.py
git commit -m "add research loop integration test"
```
