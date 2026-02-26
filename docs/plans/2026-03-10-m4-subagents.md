# M4: Claude Code Subagents Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build conversational interface to the trading agent via 5 rich subagent prompts, a read-only DB query helper, hooks, and persistent memory files.

**Architecture:** query.py wraps existing Storage methods as CLI. 5 subagent prompts reference query.py + existing CLIs. Hooks fire on file events. Memory files persist experiment context across sessions.

**Tech Stack:** Python 3.12+, DuckDB (via existing Storage), Claude Code agents/hooks/memory

---

### Task 1: query.py — Scaffold + experiments subcommand

**Files:**
- Create: `query.py`
- Create: `tests/test_query.py`

**Step 1: Write the failing test**

```python
# tests/test_query.py
import json
import subprocess
import tempfile
import pytest
from src.data.db import Storage


@pytest.fixture
def db_with_experiments(tmp_path):
    db_path = str(tmp_path / "test.duckdb")
    db = Storage(db_path)
    db.store_experiment("exp-001", "0.1", {"weights": {"trend": 0.40}}, "increase trend weight")
    db.update_experiment_decision("exp-001", "rejected", {"sharpe": 0.5})
    db.store_experiment("exp-002", "0.1", {"thresholds": {"buy": 75}}, "raise buy threshold")
    db.update_experiment_decision("exp-002", "promoted", {"sharpe": 1.2})
    db.store_experiment("exp-003", "0.2", {"weights": {"volatility": 0.20}}, "increase vol weight")
    yield db_path
    db.close()


def test_experiments_last(db_with_experiments):
    result = subprocess.run(
        ["python", "query.py", "experiments", "--last", "2", "--db", db_with_experiments],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data) == 2


def test_experiment_by_id(db_with_experiments):
    result = subprocess.run(
        ["python", "query.py", "experiment", "--id", "exp-001", "--db", db_with_experiments],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["experiment_id"] == "exp-001"


def test_experiment_not_found(db_with_experiments):
    result = subprocess.run(
        ["python", "query.py", "experiment", "--id", "exp-999", "--db", db_with_experiments],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "not found" in result.stderr.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_query.py -v`
Expected: FAIL — `query.py` doesn't exist

**Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""Read-only query helper for Claude Code subagents."""
import argparse
import json
import sys
from src.data.db import Storage

DEFAULT_DB = "data/trading_agent.duckdb"


def cmd_experiments(db: Storage, args):
    rows = db.get_recent_experiments(limit=args.last)
    print(json.dumps(rows, indent=2, default=str))


def cmd_experiment(db: Storage, args):
    row = db.get_experiment(args.id)
    if row is None:
        print(f"Experiment '{args.id}' not found", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(row, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description="Query trading agent DB (read-only)")
    parser.add_argument("--db", default=DEFAULT_DB, help="DB path")
    sub = parser.add_subparsers(dest="command")

    p_exps = sub.add_parser("experiments", help="List recent experiments")
    p_exps.add_argument("--last", type=int, default=10)

    p_exp = sub.add_parser("experiment", help="Get experiment by ID")
    p_exp.add_argument("--id", required=True)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    db = Storage(args.db)
    try:
        {"experiments": cmd_experiments, "experiment": cmd_experiment}[args.command](db, args)
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_query.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add query.py tests/test_query.py
git commit -m "feat: query.py scaffold + experiments subcommand"
```

---

### Task 2: query.py — strategy + scores subcommands

**Files:**
- Modify: `query.py`
- Modify: `tests/test_query.py`

**Step 1: Write the failing tests**

```python
# append to tests/test_query.py

@pytest.fixture
def db_with_strategies(tmp_path):
    db_path = str(tmp_path / "test.duckdb")
    db = Storage(db_path)
    db.store_strategy_version("0.1", "abc123", {"sharpe": 0.8})
    db.store_strategy_version("0.2", "def456", {"sharpe": 1.1})
    yield db_path
    db.close()


def test_strategy_current(db_with_strategies):
    result = subprocess.run(
        ["python", "query.py", "strategy", "--current", "--db", db_with_strategies],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["version"] == "0.2"


def test_strategy_history(db_with_strategies):
    result = subprocess.run(
        ["python", "query.py", "strategy", "--history", "--db", db_with_strategies],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data) == 2


@pytest.fixture
def db_with_scores(tmp_path):
    from datetime import datetime
    db_path = str(tmp_path / "test.duckdb")
    db = Storage(db_path)
    db.store_score(datetime(2026, 3, 1), "AAPL", "trend", 75.0, 0.8, {"momentum": 80})
    db.store_score(datetime(2026, 3, 1), "AAPL", "volatility", 60.0, 0.7, {"vol": 25})
    db.store_score(datetime(2026, 3, 2), "AAPL", "trend", 72.0, 0.75, {"momentum": 76})
    yield db_path
    db.close()


def test_scores_by_ticker(db_with_scores):
    result = subprocess.run(
        ["python", "query.py", "scores", "--ticker", "AAPL", "--last", "5", "--db", db_with_scores],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data) == 3
    assert all(r["ticker"] == "AAPL" for r in data)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_query.py::test_strategy_current tests/test_query.py::test_strategy_history tests/test_query.py::test_scores_by_ticker -v`
Expected: FAIL — commands not recognized

**Step 3: Implement strategy + scores commands**

Add to `query.py` before `main()`:

```python
def cmd_strategy(db: Storage, args):
    if args.current:
        row = db.get_latest_strategy_version()
        if row is None:
            print("No strategy versions found", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(row, indent=2, default=str))
    elif args.history:
        rows = db.get_strategy_versions()
        print(json.dumps(rows, indent=2, default=str))
    else:
        print("Specify --current or --history", file=sys.stderr)
        sys.exit(1)


def cmd_scores(db: Storage, args):
    # Get scores for a specific ticker, most recent first
    rows = db.conn.execute(
        "SELECT * FROM scores WHERE ticker = ? ORDER BY run_date DESC LIMIT ?",
        [args.ticker, args.last]
    ).fetchdf().to_dict("records")
    print(json.dumps(rows, indent=2, default=str))
```

Add subparsers in `main()`:

```python
    p_strat = sub.add_parser("strategy", help="Query strategy versions")
    p_strat.add_argument("--current", action="store_true")
    p_strat.add_argument("--history", action="store_true")

    p_scores = sub.add_parser("scores", help="Query scores by ticker")
    p_scores.add_argument("--ticker", required=True)
    p_scores.add_argument("--last", type=int, default=10)
```

Update the dispatch dict:

```python
    {"experiments": cmd_experiments, "experiment": cmd_experiment,
     "strategy": cmd_strategy, "scores": cmd_scores}[args.command](db, args)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_query.py -v`
Expected: PASS (all 6 tests)

**Step 5: Commit**

```bash
git add query.py tests/test_query.py
git commit -m "feat: query.py strategy + scores subcommands"
```

---

### Task 3: Upgrade portfolio-analyst.md

**Files:**
- Modify: `.claude/agents/portfolio-analyst.md`

**Step 1: Write the upgraded prompt**

```markdown
# Portfolio Analyst

You are the portfolio analyst for the Quant Autoresearch Agent. You score stocks and generate buy/hold/sell recommendations using the current promoted strategy.

## Available Commands

### Run analysis
```bash
python analyze.py TICKER1 TICKER2 TICKER3 [--strategy PATH] [--days 365]
```
Default strategy: `strategies/v0.1.yaml`. Use `--strategy` to specify another.

### Query past scores
```bash
python query.py scores --ticker AAPL --last 10
```

### Check current strategy
```bash
python query.py strategy --current
```

## Scoring System

Each stock is scored 0-100 on 6 signals, combined using strategy weights:
- **Trend** (default 0.35): momentum, SMA structure, volume confirmation, volatility contraction
- **Relative Strength** (0.10): 3m/6m/12m excess returns vs SPY
- **Volatility** (0.15): annualized vol, max drawdown, stop-loss distance
- **Liquidity** (0.10): dollar volume (log scale) + consistency
- **Fundamentals** (0.20): stubbed at 50 (future milestone)
- **Sentiment** (0.10): stubbed at 50 (future milestone)

## Thresholds
- Composite > buy threshold (default 70): **BUY** — strong signals across the board
- Composite between sell and buy: **HOLD** — mixed signals
- Composite < sell threshold (default 40): **SELL** — weak trend, poor risk/reward

## Interpreting Results

For each stock, explain:
1. The action and confidence level
2. Which signals are strongest/weakest and why
3. The risk parameters (stop loss, position size suggestion)
4. Invalidation condition — what would flip this call

For the portfolio as a whole:
1. Strongest and weakest holdings
2. Any risk warnings (sector concentration, correlation, borderline scores)
3. Whether the strategy version has changed since last analysis

## Rules
- Never invent data — all numbers come from the Python pipeline
- If data is missing or stale, say so explicitly
- Flag borderline calls (within 5 points of a threshold)
- When comparing to past analyses, use `python query.py scores --ticker X`
- If the user asks about strategy details, use `python query.py strategy --current`
```

**Step 2: No test needed (markdown file)**

**Step 3: Commit**

```bash
git add .claude/agents/portfolio-analyst.md
git commit -m "feat: upgrade portfolio-analyst agent prompt"
```

---

### Task 4: Upgrade risk-manager.md

**Files:**
- Modify: `.claude/agents/risk-manager.md`

**Step 1: Write the upgraded prompt**

```markdown
# Risk Manager

You are the risk manager for the Quant Autoresearch Agent. You review portfolio-analyst output for portfolio-level risks and flag concerns.

## Available Commands

### Run analysis (risk review is automatic)
```bash
python analyze.py TICKER1 TICKER2 TICKER3
```

### Query past recommendations
```bash
python query.py scores --ticker AAPL --last 10
```

### Check experiments for strategy changes
```bash
python query.py experiments --last 5
```

## What to Check

1. **Sector concentration** — max 40% in one sector. Flag if 3+ stocks in same industry.
2. **Correlation risk** — flag pairs likely to move together (same sector, similar market cap, overlapping business)
3. **Borderline scores** — would +-2 points on a signal flip buy→hold or hold→sell? If yes, flag as unstable.
4. **Total allocation** — position sizes must not exceed 100%. Warn if concentrated in a few names.
5. **Liquidity** — can all positions be entered/exited without moving the price? Check dollar volume.
6. **Turnover** — compare current recommendations vs previous run. High turnover = higher costs.

## How to Present Findings

- Lead with the most critical risk, not a list dump
- For each risk flagged: state the concern, quantify it, suggest mitigation
- Distinguish between hard blocks (e.g., 60% in one sector) and soft warnings (e.g., two correlated names)
- If everything looks clean, say so briefly — don't manufacture concerns

## Rules
- Be conservative — flag anything questionable
- Never override quantitative scores — your job is portfolio awareness
- If the user asks "is this safe?", answer honestly with specific numbers
- Reference the risk warnings from the analyze.py output, don't re-derive them
```

**Step 2: No test needed**

**Step 3: Commit**

```bash
git add .claude/agents/risk-manager.md
git commit -m "feat: upgrade risk-manager agent prompt"
```

---

### Task 5: Create signal-researcher.md

**Files:**
- Create: `.claude/agents/signal-researcher.md`

**Step 1: Write the prompt**

```markdown
# Signal Researcher

You are the signal researcher for the Quant Autoresearch Agent. You propose strategy experiments — one narrow hypothesis at a time — and explain your reasoning.

## Available Commands

### View experiment history
```bash
python query.py experiments --last 10
```

### View specific experiment
```bash
python query.py experiment --id exp-001
```

### View current strategy
```bash
python query.py strategy --current
```

### View strategy version history
```bash
python query.py strategy --history
```

### Run the autoresearch loop (automated)
```bash
python research.py TICKERS --max-iterations 1 --cooldown 0
```

### Backtest a specific strategy
```bash
python backtest.py TICKERS --strategy strategies/v0.1.yaml --days 730
```

## How Experiments Work

1. You propose a config diff — one change to weights, thresholds, or filters
2. The system backtests both baseline and experiment on walk-forward windows
3. 6 validation gates decide pass/fail (Sharpe, walk-forward, drawdown, turnover, regime, paper trading)
4. If all gates pass, the strategy gets promoted to a new version

## Schema Bounds

- Weights: each 0.0–0.5, must sum to 1.0
- Thresholds: buy 50–90, sell 20–60, buy must be above sell
- Filters: min_price 1–50, min_avg_volume 100K–5M, max_annual_volatility 20–200

## Proposing Experiments

When asked to propose, follow this process:
1. Check experiment history — don't repeat rejected approaches
2. Check current config — identify what hasn't been tried
3. Propose ONE small change with a clear hypothesis
4. Explain why this change should improve performance
5. Acknowledge the risk / what could go wrong

Good proposals:
- "Increase relative_strength weight from 0.10 to 0.15 (decrease fundamentals by 0.05) — RS has been a consistent differentiator"
- "Tighten sell threshold from 40 to 45 — reduce holding period for weak stocks"
- "Add min_price filter of 10 — eliminate penny stock noise"

Bad proposals:
- Changing 3 weights at once (not narrow)
- Setting a weight to 0.0 (removes a signal entirely)
- Ignoring that the same change was recently rejected

## Rules
- Never propose changes outside schema bounds
- One change at a time — compound experiments are forbidden
- Always check recent experiments first to avoid repeats
- Be honest about uncertainty — "I think this will help because..." not "this will definitely..."
- If you've run out of ideas, say so — don't force bad proposals
```

**Step 2: No test needed**

**Step 3: Commit**

```bash
git add .claude/agents/signal-researcher.md
git commit -m "feat: create signal-researcher agent prompt"
```

---

### Task 6: Create backtest-auditor.md

**Files:**
- Create: `.claude/agents/backtest-auditor.md`

**Step 1: Write the prompt**

```markdown
# Backtest Auditor

You are the backtest auditor for the Quant Autoresearch Agent. You run backtests, compare strategies, and explain metrics.

## Available Commands

### Backtest a strategy
```bash
python backtest.py TICKERS --strategy strategies/v0.1.yaml --days 730
```

### Compare two strategies (run both, then compare)
```bash
python backtest.py TICKERS --strategy strategies/v0.1.yaml --days 730
python backtest.py TICKERS --strategy strategies/v0.2.yaml --days 730
```

### View experiment results
```bash
python query.py experiment --id exp-001
```

### View experiment history
```bash
python query.py experiments --last 10
```

## Key Metrics

- **Sharpe Ratio**: risk-adjusted return. >1.0 is good, >2.0 is excellent. Below 0 means losing money.
- **CAGR**: compound annual growth rate. Raw return number.
- **Max Drawdown**: worst peak-to-trough decline. Lower is better. >30% is concerning.
- **Hit Rate**: % of positions that were profitable. >50% means more winners than losers.
- **Monthly Turnover**: how often positions change. High turnover = high transaction costs.
- **Total Return**: cumulative return over the test period.

## Walk-Forward Validation

Backtests use rolling windows (default: 6m train, 2m validation, 1m test, 1m step).
- Each window is independent — no future data leakage
- A strategy must win in >=75% of windows to pass the walk-forward gate
- Look for consistency across windows, not just aggregate numbers

## 6 Validation Gates

| Gate | Pass Condition |
|---|---|
| Sharpe | experiment > baseline |
| Walk-forward | wins >=75% of windows |
| Drawdown | not >1.5x baseline max drawdown |
| Turnover | not >2x baseline monthly turnover |
| Regime diversity | wins in both up and down markets |
| Paper trading | stubbed (always passes until M5) |

## How to Present Results

1. Lead with the headline: did the experiment beat baseline?
2. Show the key metrics comparison (table format)
3. Highlight per-window consistency — is it winning everywhere or just one window?
4. Flag any gates that failed or barely passed
5. If comparing strategies, give a clear recommendation

## Rules
- Never approximate or estimate metrics — always run the backtest
- If a backtest fails or returns empty, investigate the data (check ticker validity, date range)
- Be skeptical of strategies that look "too good" — check for overfitting signals (one window carrying the average, extreme turnover)
- Present drawdown as a percentage, not a decimal (e.g., "12% drawdown" not "0.12")
```

**Step 2: No test needed**

**Step 3: Commit**

```bash
git add .claude/agents/backtest-auditor.md
git commit -m "feat: create backtest-auditor agent prompt"
```

---

### Task 7: Create strategy-promoter.md

**Files:**
- Create: `.claude/agents/strategy-promoter.md`

**Step 1: Write the prompt**

```markdown
# Strategy Promoter

You are the strategy promoter for the Quant Autoresearch Agent. You review experiment results and decide whether to promote, reject, or flag for further review.

## Available Commands

### View experiment details
```bash
python query.py experiment --id exp-001
```

### View recent experiments
```bash
python query.py experiments --last 10
```

### View strategy history
```bash
python query.py strategy --history
```

### View current strategy
```bash
python query.py strategy --current
```

### Backtest for manual verification
```bash
python backtest.py TICKERS --strategy strategies/v0.1.yaml --days 730
```

## Decision Framework

### Auto-reject (no discretion)
- Any hard gate fails → rejected immediately
- Config outside schema bounds → rejected
- No valid backtest results → rejected

### Promotion criteria (all must hold)
- All 6 gates pass
- Sharpe improvement is meaningful (not just noise)
- Consistent across windows (not one outlier pulling the average)
- Drawdown and turnover are reasonable relative to baseline

### What to write in decision narratives
- Which gates passed and by how much
- The specific metric improvements (numbers, not vibes)
- Any concerns even if gates passed (barely passing, high variance across windows)
- What this change means for the strategy's character (e.g., "more aggressive", "tighter risk control")

## Memory Files

After making a decision, update the memory files:
- **`.claude/memory/experiment-log.md`** — append the experiment result
- **`.claude/memory/strategy-insights.md`** — add/update any learned pattern (e.g., "increasing trend weight helped Sharpe by 0.15")
- **`.claude/memory/known-issues.md`** — note any issues encountered

## Rules
- Never promote a strategy that fails any gate, regardless of how good other metrics look
- Be skeptical of small Sharpe improvements (<0.05) — likely noise
- If an experiment barely passes all gates, note the concern in the decision narrative
- After promotion, verify the new strategy file exists in `strategies/`
- Check that the version number was bumped correctly
```

**Step 2: No test needed**

**Step 3: Commit**

```bash
git add .claude/agents/strategy-promoter.md
git commit -m "feat: create strategy-promoter agent prompt"
```

---

### Task 8: Create Claude Code hooks

**Files:**
- Create or modify: `.claude/settings.json` (or wherever Claude Code hooks are configured — check docs during implementation)

**Step 1: Research Claude Code hook format**

Before implementing, check how Claude Code hooks work:
- Run `cat ~/.claude/settings.json` to see existing format
- Check if hooks go in project `.claude/settings.json` or global settings
- Hooks typically fire on tool events (e.g., Write tool writing to certain paths)

**Step 2: Create post-experiment hook**

The hook should:
- Trigger when files are written to `experiments/` directory
- Run: `python -c "import sys, yaml; from src.research.schema import validate_config_diff; from src.strategy.config import load_strategy; c = load_strategy('strategies/v0.1.yaml'); diff = yaml.safe_load(open(sys.argv[1])); errs = validate_config_diff({'weights': c.weights, 'thresholds': c.thresholds, 'filters': c.filters}, diff); print('Schema errors: ' + str(errs)) if errs else print('Config valid')" experiments/exp-NNN/config.yaml`

Simplified alternative: a small script `scripts/validate_experiment.py`:

```python
#!/usr/bin/env python3
"""Validate an experiment config against schema bounds."""
import sys
import yaml
from src.research.schema import validate_config_diff
from src.strategy.config import load_strategy

if len(sys.argv) < 2:
    print("Usage: validate_experiment.py <config.yaml>")
    sys.exit(1)

baseline = load_strategy("strategies/v0.1.yaml")
baseline_dict = {"weights": baseline.weights, "thresholds": baseline.thresholds, "filters": baseline.filters}
diff = yaml.safe_load(open(sys.argv[1]))
errors = validate_config_diff(baseline_dict, diff)
if errors:
    print(f"WARN: Schema validation errors: {errors}")
else:
    print("Config valid")
```

**Step 3: Create post-promote hook**

The hook should:
- Trigger when files are written to `strategies/` directory
- Append to `.claude/memory/experiment-log.md`

Script `scripts/log_promotion.py`:

```python
#!/usr/bin/env python3
"""Log a strategy promotion to memory."""
import sys
import json
from datetime import datetime
from src.data.db import Storage

db = Storage()
latest = db.get_latest_strategy_version()
db.close()
if latest:
    entry = f"- **{latest['version']}** promoted {datetime.now().strftime('%Y-%m-%d')} — Sharpe: {json.loads(latest.get('metrics', '{}')).get('sharpe', '?') if isinstance(latest.get('metrics'), str) else latest.get('metrics', {}).get('sharpe', '?')}\n"
    memory_path = ".claude/memory/experiment-log.md"
    with open(memory_path, "a") as f:
        f.write(entry)
    print(f"Logged promotion: {latest['version']}")
```

**Step 4: Configure hooks in Claude Code settings**

Create/update `.claude/settings.json` with hook config. Exact format depends on Claude Code's hook mechanism — look it up during implementation. The intent:

```json
{
  "hooks": {
    "post-write": [
      {
        "match": "experiments/*/config.yaml",
        "command": "python scripts/validate_experiment.py $FILE"
      },
      {
        "match": "strategies/v*.yaml",
        "command": "python scripts/log_promotion.py"
      }
    ]
  }
}
```

**Step 5: Commit**

```bash
mkdir -p scripts
git add scripts/validate_experiment.py scripts/log_promotion.py .claude/settings.json
git commit -m "feat: add post-experiment and post-promote hooks"
```

---

### Task 9: Create memory files

**Files:**
- Create: `.claude/memory/experiment-log.md`
- Create: `.claude/memory/strategy-insights.md`
- Create: `.claude/memory/known-issues.md`

**Step 1: Create experiment-log.md**

```markdown
# Experiment Log

Recent experiment outcomes (newest first, max 20 entries).

<!-- Entries are appended by the strategy-promoter agent and post-promote hook -->
```

**Step 2: Create strategy-insights.md**

```markdown
# Strategy Insights

Patterns learned from experiment history. Updated by strategy-promoter after decisions.

<!-- Add entries as patterns emerge. Remove entries that are disproven. -->

## Baseline (v0.1)
- Weights: trend=0.35, rel_strength=0.10, volatility=0.15, liquidity=0.10, fundamentals=0.20, sentiment=0.10
- Thresholds: buy=70, sell=40
```

**Step 3: Create known-issues.md**

```markdown
# Known Issues

Data gaps, recurring failures, and things that don't work. Updated by any agent.

<!-- Add entries when issues are discovered. Remove when resolved. -->

## Stubbed Signals
- Fundamentals signal always returns 50 (not yet implemented)
- Sentiment signal always returns 50 (not yet implemented)
- Paper trading gate always passes (stubbed until M5)
```

**Step 4: Commit**

```bash
mkdir -p .claude/memory
git add .claude/memory/experiment-log.md .claude/memory/strategy-insights.md .claude/memory/known-issues.md
git commit -m "feat: create memory files for cross-session context"
```

---

### Task 10: Integration test — verify all agents and query.py

**Files:**
- Create: `tests/test_m4_integration.py`

**Step 1: Write the integration test**

```python
# tests/test_m4_integration.py
"""Verify M4 components are wired up correctly."""
import json
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
import pytest
from src.data.db import Storage


@pytest.fixture
def populated_db(tmp_path):
    db_path = str(tmp_path / "test.duckdb")
    db = Storage(db_path)
    # Add experiments
    db.store_experiment("exp-001", "0.1", {"weights": {"trend": 0.40}}, "increase trend weight")
    db.update_experiment_decision("exp-001", "rejected", {"sharpe": 0.5})
    db.store_experiment("exp-002", "0.1", {"thresholds": {"buy": 75}}, "raise buy threshold")
    db.update_experiment_decision("exp-002", "promoted", {"sharpe": 1.2})
    # Add strategy version
    db.store_strategy_version("0.1", "abc123", {"sharpe": 0.8})
    db.store_strategy_version("0.2", "def456", {"sharpe": 1.1})
    # Add scores
    db.store_score(datetime(2026, 3, 1), "AAPL", "trend", 75.0, 0.8, {"momentum": 80})
    yield db_path
    db.close()


def test_query_all_subcommands(populated_db):
    """All 4 query.py subcommands return valid JSON."""
    commands = [
        ["python", "query.py", "experiments", "--last", "5", "--db", populated_db],
        ["python", "query.py", "experiment", "--id", "exp-001", "--db", populated_db],
        ["python", "query.py", "strategy", "--current", "--db", populated_db],
        ["python", "query.py", "strategy", "--history", "--db", populated_db],
        ["python", "query.py", "scores", "--ticker", "AAPL", "--db", populated_db],
    ]
    for cmd in commands:
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0, f"{cmd} failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert data is not None


def test_agent_prompts_exist():
    """All 5 agent prompt files exist and are non-empty."""
    agents = [
        ".claude/agents/portfolio-analyst.md",
        ".claude/agents/risk-manager.md",
        ".claude/agents/signal-researcher.md",
        ".claude/agents/backtest-auditor.md",
        ".claude/agents/strategy-promoter.md",
    ]
    for path in agents:
        p = Path(path)
        assert p.exists(), f"Missing agent prompt: {path}"
        assert p.stat().st_size > 100, f"Agent prompt too short: {path}"


def test_memory_files_exist():
    """All 3 memory files exist."""
    files = [
        ".claude/memory/experiment-log.md",
        ".claude/memory/strategy-insights.md",
        ".claude/memory/known-issues.md",
    ]
    for path in files:
        assert Path(path).exists(), f"Missing memory file: {path}"


def test_hook_scripts_exist():
    """Hook helper scripts exist."""
    scripts = [
        "scripts/validate_experiment.py",
        "scripts/log_promotion.py",
    ]
    for path in scripts:
        assert Path(path).exists(), f"Missing hook script: {path}"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_m4_integration.py -v`
Expected: Should pass if all previous tasks were completed correctly. If anything fails, fix it.

**Step 3: Commit**

```bash
git add tests/test_m4_integration.py
git commit -m "test: M4 integration test for agents, query, memory, hooks"
```

---

## Summary

| Task | What | Files |
|---|---|---|
| 1 | query.py scaffold + experiments | `query.py`, `tests/test_query.py` |
| 2 | query.py strategy + scores | `query.py`, `tests/test_query.py` |
| 3 | Upgrade portfolio-analyst.md | `.claude/agents/portfolio-analyst.md` |
| 4 | Upgrade risk-manager.md | `.claude/agents/risk-manager.md` |
| 5 | Create signal-researcher.md | `.claude/agents/signal-researcher.md` |
| 6 | Create backtest-auditor.md | `.claude/agents/backtest-auditor.md` |
| 7 | Create strategy-promoter.md | `.claude/agents/strategy-promoter.md` |
| 8 | Create hooks + helper scripts | `scripts/`, `.claude/settings.json` |
| 9 | Create memory files | `.claude/memory/` |
| 10 | Integration test | `tests/test_m4_integration.py` |
