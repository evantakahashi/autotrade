# M3: Autoresearch Loop — Design

Long-running autonomous loop that proposes, tests, and promotes/rejects strategy improvements.

## Decisions

| Decision | Choice |
|---|---|
| LLM integration | Anthropic SDK (loop) + Claude Code subagents (manual) |
| LLM model | Sonnet for automated loop (fast/cheap) |
| Parameter bounds | Schema-validated (weights 0-0.5, sum=1, thresholds 20-90) |
| Hypothesis context | Structured summary built from DuckDB, not raw history |
| Regime classification | SPY return > 0 over window = up, else down |
| Paper trading gate | Stubbed in M3, full implementation in M5 |

## Components

### ExperimentManager (`experiment.py`)
- Assigns sequential IDs (exp-001, exp-002, ...)
- Creates `experiments/exp-NNN-description/` with config.yaml, hypothesis.md
- Reads/writes experiment records to DuckDB
- Validates proposed configs against schema bounds

### Proposer (`proposer.py`)
- Builds structured context summary from DuckDB via `context.py`
- Calls Anthropic SDK with system prompt + context
- Parses response into config diff + hypothesis text
- Schema-validates proposed config

### Auditor (`auditor.py`)
- Runs M2 Backtester on baseline AND experiment configs
- Calls `compare_strategies()` from M2
- Applies 6 validation gates
- Returns structured verdict: pass/fail per gate + overall

### Promoter (`promoter.py`)
- Any hard gate fail → auto-reject (no LLM)
- All gates pass → Anthropic SDK writes decision narrative
- If promoted: copies config to `strategies/vX.Y.yaml`, updates `current` symlink
- Writes `decision.md` to experiment dir

### Loop (`loop.py`)
```
while True:
    context = build_context_summary(db)
    proposal = proposer.propose(context)
    experiment = manager.create(proposal)
    verdict = auditor.evaluate(experiment, baseline)
    decision = promoter.decide(verdict)
    manager.record_decision(experiment, decision)
    if consecutive_rejections >= 10: pause
    cooldown(1 hour)
```

## Schema Validation Bounds

```python
BOUNDS = {
    "weights": {"min": 0.0, "max": 0.5},
    "weights_sum": 1.0,
    "thresholds.buy": {"min": 50, "max": 90},
    "thresholds.sell": {"min": 20, "max": 60},
    "filters.min_price": {"min": 1.0, "max": 50.0},
    "filters.min_avg_volume": {"min": 100000, "max": 5000000},
}
```

## Validation Gates

| Gate | Check | Auto-reject if |
|---|---|---|
| Sharpe | experiment / baseline on test | <= 1.0 ratio |
| Walk-forward | % windows experiment wins | < 75% |
| Drawdown | experiment max DD | > 1.5x baseline |
| Turnover | monthly turnover | > 2x baseline |
| Regime | wins in up AND down windows | fails either |
| Paper trading | N days live confirmation | stubbed M3, enforced M5 |

## Files

```
src/research/
├── loop.py          # main while-True loop
├── proposer.py      # LLM experiment proposals
├── experiment.py    # experiment creation/tracking/validation
├── auditor.py       # backtest + gate evaluation
├── promoter.py      # LLM promotion decisions
├── context.py       # structured context builder
├── schema.py        # config schema validation
research.py          # CLI entrypoint
```

## Data Flow

```
research.py
  └─ loop.py
      ├─ context.py: DuckDB → summary
      ├─ proposer.py: summary → Anthropic SDK → config diff
      ├─ schema.py: validate bounds
      ├─ experiment.py: create dir + DB record
      ├─ auditor.py: backtester × 2 → compare → gates → verdict
      ├─ promoter.py: verdict → reject or (SDK → decision → promote)
      ├─ experiment.py: record to DB + files
      └─ cooldown
```
