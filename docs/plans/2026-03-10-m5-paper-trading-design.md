# M5: Paper Trading + Hardening — Design

Shadow portfolio validation gate + operational resilience for the long-running research loop.

## Decisions

| Decision | Choice |
|---|---|
| Shadow portfolio model | Daily snapshots, equal-weight at close |
| Paper trading duration | 10 trading days |
| Primary gate | Non-negative return AND <1% underperformance vs baseline |
| Secondary checks | Beat baseline (logged), directional consistency % (logged) |
| Loop during paper trading | Continues proposing, discards in-flight if baseline changes |
| Concurrent paper trades | One at a time, second gets discarded |
| State storage | DuckDB (paper_trades + loop_state tables) |
| Crash recovery | Check DB state on startup, resume paper trading |
| Graceful shutdown | SIGINT flag, clean exit, state preserved |
| Logging | Structured, file + console, rotating |

## Components

### 1. Shadow Portfolio (`paper_trader.py`)

Each day during paper trading:
1. Fetch fresh bars from Alpaca for experiment tickers
2. Run both baseline and experiment strategies on latest data
3. Record what each would buy — equal-weight positions at close
4. Track daily portfolio returns for both
5. Store snapshots in `paper_trades` DuckDB table

### 2. Paper Trading Gate

**Primary (hard gate)**:
- Experiment cumulative return >= 0
- Experiment doesn't underperform baseline by >1%

**Secondary (logged, not gates)**:
- Whether experiment beat baseline (cumulative)
- Directional consistency (% of days experiment outperformed)

### 3. New Decision State

Promoter gains third outcome: `"paper_testing"` alongside `"rejected"` and `"promoted"`.

Flow:
1. Experiment passes 5 backtest gates → promoter returns `"paper_testing"`
2. Recorded in DB with `decision = "paper_testing"`, `paper_start_date`
3. After 10 trading days → resolution: promote or reject

### 4. Loop Integration

**Main loop changes:**
- Each iteration, before proposing, check if any experiment is `paper_testing`
- If yes: fetch today's bars, record snapshot, check if 10 days elapsed
- If 10 days done: evaluate gate, promote or reject
- Loop continues proposing new experiments against current baseline during paper trading

**On promotion (baseline changes):**
- In-flight experiments (backtested against old baseline) marked `"invalidated"` in DB
- Loop continues against new baseline

**One paper trade at a time.** Second experiment passing 5 gates while one is paper trading → discarded.

### 5. Crash Recovery

- On startup, `ResearchLoop` checks DB `loop_state` table
- If experiment in `paper_testing`: resume monitoring it
- `loop_state` table tracks: status, current paper-trading experiment, last iteration time, consecutive rejections

### 6. Graceful Shutdown

- SIGINT/SIGTERM handler in `research.py` sets `shutdown_requested` flag
- Loop checks flag before each phase (propose, backtest, paper trade check)
- On shutdown: logs state, closes DB, exits 0
- Paper-trading experiment stays in `paper_testing` state, resumes on next launch

### 7. Logging

- Structured logging: iteration count, experiment ID, decision, duration
- File output: `logs/research.log` (rotating)
- Warnings for: rate limits, empty results, approaching rejection limit

## Data Layer

**New table — `paper_trades`:**

| Column | Type |
|---|---|
| experiment_id | VARCHAR |
| trade_date | DATE |
| baseline_positions | JSON |
| experiment_positions | JSON |
| baseline_return | DOUBLE |
| experiment_return | DOUBLE |
| baseline_cumulative | DOUBLE |
| experiment_cumulative | DOUBLE |

**New table — `loop_state`:**

| Column | Type |
|---|---|
| loop_id | VARCHAR PK |
| status | VARCHAR |
| paper_trading_experiment | VARCHAR |
| paper_start_date | DATE |
| last_iteration_at | TIMESTAMP |
| consecutive_rejections | INTEGER |

**Experiments table changes:**
- New decision values: `"paper_testing"`, `"invalidated"`

## Files

```
src/research/
├── loop.py              # modified — paper trading check, crash recovery, graceful shutdown
├── paper_trader.py      # NEW — shadow portfolio tracking + gate evaluation
├── auditor.py           # modified — paper trading gate becomes real
├── promoter.py          # modified — "paper_testing" decision state
src/data/
├── db.py                # modified — paper_trades + loop_state tables + methods
research.py              # modified — SIGINT handler, logging setup
logs/                    # NEW — rotating log files (gitignored)
```
