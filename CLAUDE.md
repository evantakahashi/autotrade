# Quant Autoresearch Agent

Agentic research system for stock-selection and portfolio decision support. Analyzes user-provided stocks, outputs buy/hold/sell recommendations using quant logic, and iteratively improves the strategy via an autoresearch loop with strict anti-overfitting safeguards.

## Core Principles

- **Research/decision-support system**, NOT an autonomous trading bot
- LLM orchestrates, explains, and proposes experiments; signals come from structured data and code
- Every strategy change validated before adoption — conservative promotion
- Prefer simple testable logic over vague LLM intuition
- Portfolio-first, market-scan second
- Anti-overfitting is non-negotiable

## Workflow

### Phase 1: Portfolio Analysis (steps 1-5)
1. **User input** — stock list/portfolio, optional positions/cash/risk prefs, run type (portfolio review / watchlist scan / research run)
2. **Data ingestion** — price/volume history, benchmarks (SPY/QQQ/sector ETFs), optional fundamentals, optional news/sentiment
3. **Portfolio-analyst scores each stock** — trend/momentum, relative strength, vol/drawdown, liquidity, optional fundamentals/sentiment → buy/hold/sell + confidence + breakdown + rationale + invalidation
4. **Risk-manager reviews** — concentration, correlation, turnover, liquidity, recommendation stability
5. **Portfolio report** — strongest/weakest holding, holds, sell signals, buy candidates, changes since last run

### Phase 2: Autoresearch Loop (steps 6-10)
6. **Signal-researcher proposes one small change** — narrow hypothesis (adjust weight, add filter, tighten threshold). One change at a time.
7. **Experiment version created** — strategy code in isolated branch/file (e.g. `strategy_v0_4_exp_rel_strength.py`)
8. **Backtest-auditor validates** — replay historical data with buy/hold/sell rules on rolling windows
9. **Compare baseline vs experiment** — return, drawdown, turnover, hit rate, regime stability, transaction cost survival
10. **Promoter decides** — reject (worse/unstable), paper-test (promising but unproven), promote (beats baseline robustly → new default)

## Agent Roles

- **portfolio-analyst** — applies current strategy, scores stocks, generates recommendations
- **signal-researcher** — proposes strategy experiments (one hypothesis at a time)
- **backtest-auditor** — runs walk-forward validation, compares baseline vs experiment
- **risk-manager** — reviews portfolio-level risk, blocks dangerous recommendations
- **strategy-promoter** — decides reject/paper-test/promote based on validation gates

## Validation Gates (for strategy promotion)

1. Beat baseline Sharpe on out-of-sample test period
2. Walk-forward consistency — passes in at least 3 of 4 rolling windows
3. Max drawdown doesn't worsen significantly vs baseline
4. Turnover within limits
5. Survives regime diversity — not just bull-market alpha
6. Paper trading confirmation — runs N days on live data before full promotion

## Conventions

- Python 3.12+, type hints everywhere
- `pyproject.toml` for deps (no requirements.txt)
- DuckDB for storage (gitignored)
- DataProvider ABC — all data access goes through this interface
- Scores normalized 0-100, confidence 0-1
- Strategy versions tracked as files + DuckDB metrics
- Experiments in `experiments/exp-NNN-description/` (files) + experiments table (DuckDB)

## Data

- Alpaca free tier for OHLCV bars + news (upgrade to Massive/Polygon later)
- API keys in `.env` (gitignored): `ALPACA_API_KEY`, `ALPACA_SECRET`
- DuckDB tables: bars, scores, rankings, news, experiments, strategy_versions

## Design Docs

- `docs/plans/2026-03-10-trading-agent-design.md` — original design (v1)
- `docs/plans/2026-03-10-autoresearch-design.md` — autoresearch redesign (v2)
