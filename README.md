# autotrade

Autonomous quant research agent that proposes, backtests, and promotes stock-selection strategy improvements — then lets you inspect everything through a web dashboard.

The LLM orchestrates and explains. The math is deterministic Python. Anti-overfitting is enforced by 6 hard validation gates.

## How it works

Two modes:

**Analyze** — you provide tickers, the system scores each stock on trend, relative strength, volatility, and liquidity, then outputs buy/hold/sell with confidence and rationale.

**Research** — a long-running loop where Claude proposes one narrow strategy change at a time, backtests it with walk-forward validation, runs 10 days of shadow portfolio paper trading, and only promotes changes that robustly beat the baseline. Everything else gets rejected.

## Quick start

Prerequisites: Python 3.12+, Node.js 18+, pnpm

1. Clone and install:

```bash
git clone https://github.com/evantakahashi/autotrade.git
cd autotrade
pip install -e ".[dev]"
cd frontend && pnpm install && cd ..
```

2. Set up API keys in `.env`:

```
ALPACA_API_KEY=your_key        # free tier at alpaca.markets
ALPACA_SECRET=your_secret
ANTHROPIC_API_KEY=your_key
```

3. Create the data directory:

```bash
mkdir -p data
```

4. Run — open Claude Code in the project root and talk to it:

```
> analyze AAPL, NVDA, MSFT, AMD, and GOOG

> backtest the current strategy on AAPL NVDA MSFT over the last 2 years

> run 3 research iterations on AAPL NVDA MSFT with no cooldown

> start the web dashboard
```

Claude Code dispatches the right subagent automatically. You can also call them directly:

```
> @portfolio-analyst score AAPL and NVDA and explain the rationale

> @signal-researcher propose an experiment to improve trend detection

> @backtest-auditor compare v0.1 vs v0.2

> @risk-manager review my current portfolio

> @strategy-promoter evaluate experiment exp-003
```

## Project structure

```
.claude/
  agents/               # Claude Code subagent prompts (5 roles)
  memory/               # persistent context across sessions

src/
  agents/               # portfolio analyst, risk manager, signals
  research/             # backtester, proposer, auditor, promoter, paper trader
  strategy/             # config loader, version registry
  data/                 # Alpaca provider, DuckDB storage
  api/                  # FastAPI routes

frontend/               # Next.js dashboard (v0-generated, shadcn/ui)
strategies/             # YAML strategy configs (v0.1, v0.2, ...)
experiments/            # experiment dirs (config, hypothesis, results, decision)

analyze.py              # internal CLI (called by agents)
backtest.py             # internal CLI (called by agents)
research.py             # internal CLI (called by agents)
query.py                # read-only DB queries for agents
run_api.py              # FastAPI server for the web dashboard
```

## Strategy pipeline

Each stock is scored 0-100 on 4 signals (+ 2 stubbed), combined with configurable weights:

| Signal | Weight | What it measures |
|---|---|---|
| Trend | 0.35 | Momentum, SMA structure, volume confirmation |
| Relative Strength | 0.10 | Excess returns vs SPY (3m/6m/12m) |
| Volatility | 0.15 | Annualized vol, max drawdown, stop-loss distance |
| Liquidity | 0.10 | Dollar volume + consistency |
| Fundamentals | 0.20 | Stubbed at 50 (future) |
| Sentiment | 0.10 | Stubbed at 50 (future) |

Composite > 70 = **BUY**, < 40 = **SELL**, between = **HOLD**.

## Validation gates

Every strategy change must pass all 6 gates before promotion:

| Gate | Requirement |
|---|---|
| Sharpe | Experiment beats baseline |
| Walk-forward | Wins in >= 75% of rolling windows |
| Drawdown | Max DD not > 1.5x baseline |
| Turnover | Monthly turnover not > 2x baseline |
| Regime diversity | Wins in both up and down markets |
| Paper trading | 10 days shadow portfolio: non-negative return, < 1% underperformance |

## Claude Code agents

Five subagent prompts for conversational interaction:

- `@portfolio-analyst` — score stocks and explain recommendations
- `@signal-researcher` — propose strategy experiments
- `@backtest-auditor` — run backtests and compare strategies
- `@risk-manager` — review portfolio-level risk
- `@strategy-promoter` — evaluate experiments and promote/reject

## Design choices

- **LLM proposes, code decides.** The LLM never touches scoring math or backtest metrics. It proposes config changes and writes narratives. All validation is deterministic.
- **One change at a time.** Compound experiments are forbidden. Each experiment modifies one parameter so you know exactly what caused the improvement.
- **Conservative promotion.** Most experiments get rejected. That's by design. The system favors stability over novelty.

## License

MIT
