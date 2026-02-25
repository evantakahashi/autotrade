# M4: Claude Code Subagents — Design

Conversational interface to the trading agent via 5 rich subagent prompts, a read-only DB query helper, hooks for automation, and persistent memory files.

## Decisions

| Decision | Choice |
|---|---|
| Agent depth | Rich interpreters — domain knowledge, follow-ups, suggestions |
| DB access | CLI + read-only query helper (no raw DuckDB in prompts) |
| Hooks & memory | Both included in M4 |
| Standalone use | All 5 agents usable independently, not just via loop |

## Components

### 1. Subagent Prompts (`.claude/agents/`)

5 agents, each with: role + domain context, available commands, result interpretation, presentation format, rules.

| Agent | Wraps | Standalone Use Case |
|---|---|---|
| `portfolio-analyst.md` | `analyze.py` + query helper | "analyze AAPL NVDA MSFT" |
| `risk-manager.md` | `analyze.py` output + query helper | "review risk on my last analysis" |
| `signal-researcher.md` | `proposer.py` + experiment DB | "propose an experiment to improve Sharpe" |
| `backtest-auditor.md` | `backtest.py` + `comparison.py` | "compare v0.1 vs v0.2 on 2 years" |
| `strategy-promoter.md` | `promoter.py` + experiment DB | "review exp-003 and decide" |

Existing `portfolio-analyst.md` and `risk-manager.md` get upgraded from ~30 lines to rich prompts with DB query access and domain knowledge.

### 2. Query Helper (`query.py`)

Read-only CLI thin wrapper over existing `Storage` methods:

```
python query.py experiments --last 5
python query.py strategy --current
python query.py strategy --history
python query.py scores --ticker AAPL --last 10
python query.py experiment --id exp-003
```

- No new DB logic — wraps existing methods
- Read-only, no mutations
- Agents learn 5 commands instead of DuckDB API

### 3. Hooks (`.claude/hooks/`)

**`post-experiment`** — fires after file written to `experiments/`
- Validates experiment config against schema bounds
- Warns user if config out of bounds
- Calls `src/research/schema.py` validate_config

**`post-promote`** — fires after `strategies/current` symlink changes
- Appends promotion event to `.claude/memory/experiment-log.md`
- Logs: version, date, key metrics delta vs previous

Both read-only — never mutate strategy state.

### 4. Memory Files (`.claude/memory/`)

| File | Contents | Updated by |
|---|---|---|
| `experiment-log.md` | Last ~20 experiments: ID, hypothesis, outcome, metrics | post-promote hook + strategy-promoter |
| `strategy-insights.md` | Learned patterns (e.g., "rel_strength > 0.15 helps") | strategy-promoter after decisions |
| `known-issues.md` | Data gaps, recurring failures, things that don't work | Any agent |

Rules:
- `experiment-log.md` capped at 20 entries, oldest dropped
- `strategy-insights.md` curated — disproven entries removed
- Agents read memory at session start for context

## Files

```
.claude/
├── agents/
│   ├── portfolio-analyst.md   # upgraded
│   ├── risk-manager.md        # upgraded
│   ├── signal-researcher.md   # new
│   ├── backtest-auditor.md    # new
│   └── strategy-promoter.md   # new
├── hooks/
│   ├── post-experiment.sh     # schema validation
│   └── post-promote.sh        # memory update
└── memory/
    ├── experiment-log.md
    ├── strategy-insights.md
    └── known-issues.md
query.py                        # read-only DB query CLI
tests/test_query.py
```

## Unresolved Questions

- Should hooks be `.sh` scripts or Claude Code hook config (settings.json format)? Need to check Claude Code hook mechanism.
