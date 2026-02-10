# Trading Agent Design

Weekly stock ranking engine with deterministic Python core + Claude Code subagent wrappers.

## Decisions

| Decision | Choice |
|---|---|
| Language | Python |
| Data provider | Alpaca free tier (swap to Massive/Polygon later) |
| Database | DuckDB (embedded, analytical) |
| Architecture | Python modules + Claude Code subagent wrappers |
| Fundamentals | Stubbed until Massive integration |
| Output | Terminal pretty-print + JSON files |
| Agent structure | BaseAgent ABC with `score()` / `explain()` interface |

## Project Structure

```
trading_agent/
├── src/
│   ├── agents/
│   │   ├── base.py          # BaseAgent ABC
│   │   ├── universe.py      # UniverseBuilder (filter, not score)
│   │   ├── trend.py         # TrendAgent
│   │   ├── fundamentals.py  # FundamentalsAgent (stubbed)
│   │   ├── sentiment.py     # SentimentAgent
│   │   ├── risk.py          # RiskAgent
│   │   └── ranking.py       # RankingAgent (combiner)
│   ├── data/
│   │   ├── provider.py      # DataProvider ABC
│   │   ├── alpaca.py        # AlpacaProvider
│   │   └── db.py            # DuckDB storage layer
│   ├── models/
│   │   └── types.py         # Dataclasses: Stock, AgentScore, Ranking, etc.
│   └── output/
│       ├── console.py       # Pretty-print to terminal
│       └── json_writer.py   # Save to output/ dir
├── .claude/
│   └── agents/
│       ├── universe-researcher.md
│       ├── trend-analyst.md
│       ├── sentiment-analyst.md
│       └── ranking-agent.md
├── output/                  # Generated rankings (gitignored)
├── run_ranking.py           # CLI entrypoint
├── pyproject.toml
└── .env                     # ALPACA_API_KEY, ALPACA_SECRET (gitignored)
```

## Core Interfaces

### BaseAgent

```python
class BaseAgent(ABC):
    name: str
    weight: float  # 0-1, contribution to composite

    @abstractmethod
    def score(self, universe: list[Stock], data: DataProvider) -> dict[str, AgentScore]:
        """Return {ticker: AgentScore} for each stock."""

    @abstractmethod
    def explain(self, ticker: str, score: AgentScore) -> str:
        """Human-readable explanation."""
```

### AgentScore

```python
@dataclass
class AgentScore:
    ticker: str
    agent: str
    score: float        # 0-100 normalized
    confidence: float   # 0-1
    components: dict    # sub-signals
    timestamp: datetime
```

### DataProvider

```python
class DataProvider(ABC):
    def get_bars(self, ticker, start, end, timeframe="1Day") -> pd.DataFrame
    def get_latest_quote(self, ticker) -> Quote
    def get_assets(self, filters) -> list[Asset]
    def get_news(self, ticker, start, end) -> list[NewsArticle]
    def get_fundamentals(self, ticker) -> Fundamentals  # stubbed for Alpaca
```

## Agent Details

### UniverseBuilder
- Calls `provider.get_assets()` for all tradable US stocks
- Filters: min price $5, min avg volume 500k shares/day, active, excludes OTC
- Returns ~1000-2000 stocks
- No scoring — filtering only

### TrendAgent (weight: 0.35)
- 3m/6m/12m momentum (price returns)
- Relative strength vs SPY
- Trend structure: price vs 20/50/200 SMA
- Volatility contraction: 20-day ATR as % of price
- Volume confirmation: up-day vs down-day volume ratio (20d)

### FundamentalsAgent (weight: 0.25) — STUBBED
- Returns score=50 for all stocks
- Designed for: earnings growth, revenue acceleration, estimate revisions, margins, insider activity
- Awaiting Massive/Polygon integration

### SentimentAgent (weight: 0.20)
- News volume: 7d/30d article count vs trailing avg
- News recency: hours since last article
- Headline sentiment: keyword-based positive/negative scoring
- Claude subagent adds LLM-powered interpretation on top

### RiskAgent (weight: 0.10)
- 20-day annualized volatility
- Max drawdown (6 months)
- Liquidity: avg daily dollar volume
- Distance from 52-week high
- Sector concentration flag
- Outputs: risk score, max position size, stop-loss level (2x ATR)

### RankingAgent (weight: 0.10 for relative strength)
- Composite: 0.35*trend + 0.25*fundamentals + 0.20*sentiment + 0.10*rel_strength + 0.10*risk
- Sector cap: max 3 per sector in top 10
- Correlation check: flag pairs > 0.7 over 60 days
- Output: top 10 with per-agent breakdown

## Pipeline Flow

```
run_ranking.py
  1. Load config (.env, weights)
  2. Init AlpacaProvider + DuckDB
  3. UniverseBuilder.build() → list[Stock]
  4. Fetch OHLCV bars for universe (bulk, cached in DuckDB)
  5. Run agents concurrently (concurrent.futures):
     - TrendAgent.score(universe)
     - FundamentalsAgent.score(universe)
     - SentimentAgent.score(universe)
  6. RiskAgent.score(universe)
  7. RankingAgent.combine(all_scores) → top 10
  8. Output: terminal table + JSON to output/
  9. Persist scores to DuckDB
```

## DuckDB Schema

- `bars` — OHLCV history, append-only cache
- `scores` — every agent score per run (for backtesting)
- `rankings` — final composite rankings per run
- `news` — cached headlines

## Claude Code Subagents

Each `.claude/agents/*.md` wraps a Python module:
- **universe-researcher** — explore/filter the tradable universe
- **trend-analyst** — run trend scoring, explain setups
- **sentiment-analyst** — run sentiment scoring, add LLM headline interpretation
- **ranking-agent** — run full pipeline, present with narrative

## Output Format

Terminal: ranked table + warnings (sector concentration, correlation) + per-stock explanation with "why now", risk params, invalidation.

JSON: `{date, rankings: [{rank, ticker, composite, scores, explanation, invalidation}], warnings: []}` saved to `output/ranking-YYYY-MM-DD.json`.

## Unresolved Questions

1. Alpaca free tier rate limits — may need throttling for 1000+ tickers
2. Sentiment: basic keyword list vs VADER library?
3. Correlation matrix: compute only for top ~20 candidates to avoid expense?
