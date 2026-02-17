# M2: Backtester — Design

Vectorized backtester with walk-forward validation for strategy evaluation.

## Components

### StrategyRunner
Wraps M1's PortfolioAnalyst to run on historical windows. Given strategy config + bars up to a date, returns buy/hold/sell positions with scores. No lookahead — only uses data up to the current simulation date.

### Backtester
Owns the walk-forward loop. For each rolling window:
1. Split into train / validation / test by time
2. Run StrategyRunner at end of train → initial positions
3. Step through test period, rebalance at configured frequency
4. Track portfolio value using next-day open prices
5. Pass returns to MetricsCalculator

Aggregates all windows into BacktestResult.

### MetricsCalculator
Pure functions. Takes returns series → metrics dict.

| Metric | Description |
|---|---|
| Sharpe | annualized mean return / std return |
| CAGR | (end/start)^(252/days) - 1 |
| Max drawdown | worst peak-to-trough |
| Hit rate | % of trades profitable |
| Turnover | avg monthly position changes / total positions |
| Win/loss ratio | avg winner / avg loser |

### BacktestResult
Dataclass: per-window metrics + aggregate metrics + metadata.

## Walk-Forward Windows

```
|---train---|--val--|--test--|
            |---train---|--val--|--test--|
                        |---train---|--val--|--test--|
```

Default config (in strategy YAML):
```yaml
backtest:
  train_months: 6
  validation_months: 2
  test_months: 1
  step_months: 1
  rebalance_frequency: weekly
  transaction_cost_bps: 10
```

## Position Sizing
Equal-weight MVP. All buy positions get equal allocation. Score-weighted is a future improvement.

## Transaction Costs
Flat basis points per trade. Deducted at each rebalance when positions change. No slippage model for MVP.

## Connection to M3
Backtester is a pure function: (config + data) → BacktestResult. The auditor calls it twice (baseline + experiment) and compares.

## Files
```
src/research/
├── backtester.py    # Backtester class, walk-forward loop
├── runner.py        # StrategyRunner wrapping PortfolioAnalyst
├── metrics.py       # MetricsCalculator, pure functions
└── results.py       # BacktestResult dataclass
tests/
├── test_metrics.py
├── test_runner.py
└── test_backtester.py
```

## Decisions
- Walk-forward windows: configurable, default 6m/2m/1m/1m
- Rebalance: configurable, default weekly
- Position sizing: equal-weight for MVP
- Transaction costs: configurable bps, default 10
- No slippage model for MVP
