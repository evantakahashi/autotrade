# Trading Agent

Weekly stock ranking engine: deterministic Python pipeline + Claude Code subagent wrappers.

## Architecture

- `src/agents/` — scoring agents, each extends BaseAgent ABC with `score()` and `explain()`
- `src/data/` — data provider abstraction (Alpaca now, Massive/Polygon later)
- `src/models/types.py` — shared dataclasses (Stock, AgentScore, Ranking)
- `src/output/` — console and JSON output formatters
- `.claude/agents/` — Claude Code subagent prompt files
- `run_ranking.py` — CLI entrypoint

## Conventions

- Python 3.12+, type hints everywhere
- `pyproject.toml` for deps (no requirements.txt)
- DuckDB for storage (`data/trading_agent.duckdb`, gitignored)
- DataProvider ABC in `src/data/provider.py` — all data access goes through this
- Agent weights: trend=0.35, fundamentals=0.25, sentiment=0.20, rel_strength=0.10, risk=0.10
- FundamentalsAgent is stubbed (returns 50) until Massive integration
- Scores normalized 0-100, confidence 0-1

## Data

- Alpaca free tier for OHLCV bars + news
- API keys in `.env` (gitignored): `ALPACA_API_KEY`, `ALPACA_SECRET`
- DuckDB tables: bars, scores, rankings, news

## Running

```
python run_ranking.py
```

Output goes to terminal + `output/ranking-YYYY-MM-DD.json`.

## Design Doc

See `docs/plans/2026-03-10-trading-agent-design.md` for full design.
