# Quant Autoresearch Agent — System Design

## Product Summary

Two-mode agentic research system for stock-selection and portfolio decision support.

**Mode 1 (Analyze):** User provides tickers. System scores each stock on trend/momentum, relative strength, volatility, liquidity (+ optional fundamentals/sentiment), outputs buy/hold/sell with confidence, rationale, and invalidation. Risk layer checks portfolio-level concerns.

**Mode 2 (Research):** Long-running autoresearch loop. LLM-powered signal-researcher proposes one narrow strategy change at a time. System backtests with walk-forward validation against baseline. Changes that robustly beat baseline get promoted; everything else rejected. Loop runs indefinitely.

LLM orchestrates and explains. Math is deterministic Python. Anti-overfitting enforced by 6 hard validation gates.

---

## Decisions

| Decision | Choice |
|---|---|
| Language | Python 3.12+ |
| Data provider | Alpaca free tier (Massive/Polygon later) |
| Database | DuckDB (embedded, analytical) |
| Architecture | Two processes (analyze + research) sharing core |
| Backtesting | Vectorized MVP, event-driven interface later |
| Strategy versioning | YAML config + optional code overrides |
| Experiment tracking | Files (experiments/) + DuckDB metrics |
| Autoresearch autonomy | Autonomous loop, conservative promotion, manual override |
| Backtest history | Maximum available from provider |
| UI | v0 web interface in future milestone |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    USER INTERFACE                         │
│  CLI: analyze.py / research.py                           │
│  Claude Code: subagent wrappers for conversational use   │
│  Future: v0 web UI                                       │
└──────────┬──────────────────────┬────────────────────────┘
           │                      │
    ┌──────▼──────┐      ┌───────▼────────┐
    │  ANALYZE    │      │  RESEARCH      │
    │  (on-demand)│      │  (long-running)│
    └──────┬──────┘      └───────┬────────┘
           │                      │
           │  ┌───────────────────┤
           │  │                   │
    ┌──────▼──▼───┐    ┌─────────▼─────────┐
    │ SCORING     │    │ EXPERIMENT ENGINE  │
    │ ENGINE      │    │                    │
    │             │    │ propose → create → │
    │ portfolio-  │    │ backtest → compare │
    │ analyst     │    │ → promote/reject   │
    │ risk-manager│    │                    │
    └──────┬──────┘    │ signal-researcher  │
           │           │ backtest-auditor   │
           │           │ strategy-promoter  │
           │           └─────────┬──────────┘
           │                     │
    ┌──────▼─────────────────────▼──────┐
    │          SHARED CORE              │
    │                                   │
    │  Data Layer (Alpaca → DuckDB)     │
    │  Strategy Configs (YAML + code)   │
    │  Backtester (vectorized)          │
    │  Experiment Log (files + DuckDB)  │
    └───────────────────────────────────┘
```

- Analyze and Research are independent processes sharing the same core
- Both read the current promoted strategy config
- Research writes new experiments; Analyze always uses latest promoted version
- DuckDB single-writer safe — research loop is sequential

---

## Folder Structure

```
quant-autoresearch/
├── src/
│   ├── agents/
│   │   ├── base.py              # BaseAgent ABC
│   │   ├── portfolio_analyst.py # scores stocks, buy/hold/sell
│   │   ├── risk_manager.py      # portfolio-level risk checks
│   │   └── signals/
│   │       ├── trend.py         # trend/momentum signal
│   │       ├── relative_strength.py
│   │       ├── volatility.py
│   │       ├── liquidity.py
│   │       ├── fundamentals.py  # stubbed
│   │       └── sentiment.py     # stubbed
│   ├── research/
│   │   ├── loop.py              # autoresearch main loop
│   │   ├── proposer.py          # signal-researcher logic (LLM)
│   │   ├── backtester.py        # vectorized backtester
│   │   ├── auditor.py           # compares baseline vs experiment
│   │   ├── promoter.py          # reject/paper-test/promote (LLM)
│   │   └── experiment.py        # experiment creation/tracking
│   ├── data/
│   │   ├── provider.py          # DataProvider ABC
│   │   ├── alpaca.py            # AlpacaProvider
│   │   └── db.py                # DuckDB storage
│   ├── models/
│   │   └── types.py             # dataclasses
│   ├── strategy/
│   │   ├── config.py            # loads/validates strategy YAML
│   │   └── registry.py          # tracks versions, current baseline
│   └── output/
│       ├── console.py           # terminal formatter
│       └── json_writer.py       # JSON output
├── strategies/
│   ├── v0.1.yaml                # baseline strategy config
│   └── current -> v0.1.yaml     # symlink to promoted version
├── experiments/
│   └── exp-001-description/
│       ├── config.yaml          # what changed
│       ├── hypothesis.md        # why
│       ├── results.json         # backtest metrics
│       └── decision.md          # reject/promote + reasoning
├── .claude/
│   └── agents/
│       ├── portfolio-analyst.md
│       ├── signal-researcher.md
│       ├── backtest-auditor.md
│       ├── risk-manager.md
│       └── strategy-promoter.md
├── tests/
├── output/                      # gitignored
├── analyze.py                   # on-demand portfolio analysis
├── research.py                  # long-running autoresearch loop
├── pyproject.toml
├── .env
└── CLAUDE.md
```

---

## Data Flow

### Analyze Flow
```
analyze.py NVDA AMD PLTR
  1. Load current strategy (strategies/current -> v0.1.yaml)
  2. Fetch data via AlpacaProvider → cache in DuckDB
  3. For each ticker, compute signals:
     trend + rel_strength + volatility + liquidity (+ fundamentals + sentiment)
  4. Portfolio-analyst combines signals using strategy weights → buy/hold/sell
  5. Risk-manager reviews: concentration, correlation, stability
  6. Output: terminal report + output/analysis-YYYY-MM-DD.json
  7. Persist scores to DuckDB
```

### Research Flow
```
research.py
  while True:
    1. Load baseline strategy + past experiment log
    2. Signal-researcher (LLM) proposes hypothesis + config diff
    3. Create experiments/exp-NNN-description/
    4. Backtester runs walk-forward on baseline AND experiment
    5. Auditor compares metrics across all windows
    6. Promoter (LLM) reviews → reject / paper-test / promote
    7. If promoted: copy config to strategies/vX.Y.yaml, update symlink
    8. Log everything to DuckDB + experiment dir
    9. Cooldown / rate limit check
    10. Repeat (or pause after 10 consecutive rejections)
```

---

## Strategy Versioning

### Config Format
```yaml
# strategies/v0.1.yaml
version: "0.1"
name: "baseline"
weights:
  trend: 0.35
  relative_strength: 0.10
  volatility: 0.15
  liquidity: 0.10
  fundamentals: 0.20
  sentiment: 0.10
thresholds:
  buy: 70
  hold_min: 40
  sell: 40
filters:
  min_price: 5.0
  min_avg_volume: 500000
  max_annual_volatility: 100
overrides: null  # optional path to Python file for custom scoring logic
```

### Versioning Rules
- Minor bumps (0.1 → 0.2) for config-only changes
- Major bumps (0.x → 1.0) for code-level overrides
- `strategies/current` symlink always points to promoted version
- Full version history preserved — instant rollback

### Experiment Tracking

**Files:** `experiments/exp-NNN-description/`
- `config.yaml` — the modified strategy config
- `hypothesis.md` — what and why
- `results.json` — backtest metrics for all windows
- `decision.md` — reject/promote + reasoning

**DuckDB tables:**
- `experiments` — experiment_id, parent_version, config_diff, metrics, decision, timestamp
- `strategy_versions` — version, config_hash, promoted_date, metrics_at_promotion

---

## Autoresearch Loop Safety

### Validation Gates (ALL must pass for promotion)

| Gate | Metric | Threshold |
|---|---|---|
| Out-of-sample Sharpe | experiment / baseline Sharpe on test set | > 1.0 |
| Walk-forward consistency | % of rolling windows where experiment wins | >= 75% |
| Max drawdown | experiment max drawdown | not > 1.5x baseline |
| Turnover | avg monthly turnover | within 2x baseline |
| Regime diversity | wins in up AND down market windows | must pass both |
| Paper trading | N days live-data confirmation | default 5 trading days |

### Additional Safety
- Max experiment rate: 1 per hour
- Consecutive rejection limit: 10 → pause loop, log "exhausted hypotheses"
- No compound experiments: one change at a time
- Full reproducibility: config + data snapshot hash preserved

---

## Agent Definitions

### portfolio-analyst
Applies current promoted strategy to user-provided tickers. Computes all signal scores, combines with strategy weights, generates buy/hold/sell + confidence + rationale + invalidation. **Pure Python, no LLM.**

### risk-manager
Post-processes portfolio-analyst output. Checks:
- Sector concentration (max 30% one sector)
- Correlation (flags pairs > 0.7)
- Turnover vs last run
- Liquidity adequacy
- Recommendation stability (would +-2 points flip the decision?)

**Pure Python, no LLM.**

### signal-researcher
LLM-powered. Reads experiment history, current strategy, recent performance. Proposes one narrow hypothesis as a config diff. Writes hypothesis.md. Examples:
- "increase relative_strength weight from 0.10 to 0.15"
- "add drawdown filter: reject stocks with >30% drawdown in 6 months"
- "tighten sell threshold from 40 to 45"

### backtest-auditor
Pure Python. Runs vectorized walk-forward backtest on baseline and experiment. Splits history into rolling train/validation/test windows. Computes per window: Sharpe, CAGR, max drawdown, turnover, hit rate. Outputs structured comparison.

### strategy-promoter
LLM-assisted. Reads auditor metrics, applies hard gates (auto-reject if any gate fails), then writes decision.md with reasoning. If all gates pass, promotes strategy version and updates symlink.

---

## Claude Code Integration

### Subagent Prompts (`.claude/agents/`)
Each wraps the Python modules with conversational interface:
- `portfolio-analyst.md` — run analyze.py, interpret and present results
- `signal-researcher.md` — propose experiments, explain reasoning
- `backtest-auditor.md` — run backtests, explain metrics
- `risk-manager.md` — review portfolio risk, flag concerns
- `strategy-promoter.md` — review experiment results, explain decisions

### Hooks
- `post-experiment` — after strategy file modified, auto-run validation
- `post-promote` — log promotion event, update memory

### Memory (`.claude/memory/`)
- `experiment-log.md` — recent experiments and outcomes
- `strategy-insights.md` — learned patterns ("rel_strength > 0.15 consistently helps")
- `known-issues.md` — things that don't work

---

## MVP Milestones

| # | Milestone | Scope |
|---|---|---|
| M1 | Scoring engine + CLI analysis | Data layer, all signals, portfolio-analyst, risk-manager, analyze.py |
| M2 | Backtester | Vectorized backtester, walk-forward windows, metrics |
| M3 | Autoresearch loop | Experiment engine, signal-researcher, auditor, promoter, research.py |
| M4 | Claude Code subagents | Subagent prompts for all 5 roles, conversational interface |
| M5 | Paper trading + hardening | Paper trading gate, stability checks, cooldowns |
| M6 | Web UI (v0) | Portfolio view, experiment history, strategy comparison |

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Overfitting via many experiments | 6 hard gates, walk-forward, regime diversity |
| LLM proposing nonsensical experiments | Config schema validation, bounded parameter ranges |
| Alpaca rate limits | Throttling, DuckDB caching, batch requests |
| DuckDB concurrent access | Single-writer (research is sequential), analyze reads only |
| Strategy regression | Full version history, instant rollback via symlink |
| Stale data | Cache TTL, re-fetch if > 1 day old |
| Research loop stalling | Consecutive rejection limit, hypothesis diversity tracking |
| LLM hallucinating metrics | LLM never computes metrics — only reads Python output |
