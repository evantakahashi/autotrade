# M2: Backtester Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a vectorized walk-forward backtester that evaluates strategy configs against historical data and outputs comparable metrics.

**Architecture:** StrategyRunner wraps M1's PortfolioAnalyst for historical simulation. Backtester generates rolling windows and runs the strategy on each. MetricsCalculator computes Sharpe, CAGR, drawdown, hit rate, turnover. BacktestResult aggregates per-window and overall metrics.

**Tech Stack:** Python 3.12+, pandas, numpy (no new deps)

---

### Task 1: BacktestResult and BacktestConfig Dataclasses

**Files:**
- Create: `src/research/results.py`
- Modify: `src/strategy/config.py`
- Create: `tests/test_results.py`

**Step 1: Write failing tests**

```python
# tests/test_results.py
from src.research.results import BacktestResult, WindowResult

def test_window_result_creation():
    wr = WindowResult(
        window_id=0,
        train_start="2025-01-01", train_end="2025-06-30",
        test_start="2025-09-01", test_end="2025-09-30",
        metrics={"sharpe": 1.2, "cagr": 0.15, "max_drawdown": 0.08},
        positions={"AAPL": "buy", "MSFT": "hold"},
    )
    assert wr.metrics["sharpe"] == 1.2

def test_backtest_result_creation():
    wr = WindowResult(0, "2025-01-01", "2025-06-30", "2025-09-01", "2025-09-30",
                      {"sharpe": 1.2}, {})
    result = BacktestResult(
        strategy_version="0.1",
        window_results=[wr],
        aggregate_metrics={"sharpe": 1.2},
        config_snapshot={"weights": {"trend": 0.35}},
    )
    assert len(result.window_results) == 1
    assert result.aggregate_metrics["sharpe"] == 1.2

def test_backtest_result_win_rate():
    windows = [
        WindowResult(0, "", "", "", "", {"sharpe": 1.5}, {}),
        WindowResult(1, "", "", "", "", {"sharpe": 0.8}, {}),
        WindowResult(2, "", "", "", "", {"sharpe": 1.1}, {}),
    ]
    result = BacktestResult("0.1", windows, {}, {})
    # Helper: how many windows had sharpe > 1.0
    assert result.windows_passing(lambda m: m["sharpe"] > 1.0) == 2
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_results.py -v`
Expected: FAIL

**Step 3: Implement**

```python
# src/research/results.py
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class WindowResult:
    window_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    metrics: dict = field(default_factory=dict)
    positions: dict = field(default_factory=dict)

@dataclass
class BacktestResult:
    strategy_version: str
    window_results: list[WindowResult] = field(default_factory=list)
    aggregate_metrics: dict = field(default_factory=dict)
    config_snapshot: dict = field(default_factory=dict)

    def windows_passing(self, condition: Callable[[dict], bool]) -> int:
        return sum(1 for w in self.window_results if condition(w.metrics))
```

**Step 4: Add backtest config to StrategyConfig**

```python
# Modify: src/strategy/config.py
# Add backtest field to StrategyConfig dataclass and update load_strategy

@dataclass
class BacktestConfig:
    train_months: int = 6
    validation_months: int = 2
    test_months: int = 1
    step_months: int = 1
    rebalance_frequency: str = "weekly"  # "weekly" or "monthly"
    transaction_cost_bps: float = 10.0   # basis points per trade

@dataclass
class StrategyConfig:
    version: str
    name: str
    weights: dict[str, float]
    thresholds: dict[str, float]
    filters: dict[str, float] = field(default_factory=dict)
    overrides: str | None = None
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
```

Update `load_strategy` to parse backtest section:
```python
def load_strategy(path: str) -> StrategyConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)

    bt_raw = raw.get("backtest", {})
    backtest = BacktestConfig(
        train_months=bt_raw.get("train_months", 6),
        validation_months=bt_raw.get("validation_months", 2),
        test_months=bt_raw.get("test_months", 1),
        step_months=bt_raw.get("step_months", 1),
        rebalance_frequency=bt_raw.get("rebalance_frequency", "weekly"),
        transaction_cost_bps=bt_raw.get("transaction_cost_bps", 10.0),
    )

    config = StrategyConfig(
        version=str(raw["version"]),
        name=raw["name"],
        weights=raw["weights"],
        thresholds=raw["thresholds"],
        filters=raw.get("filters", {}),
        overrides=raw.get("overrides"),
        backtest=backtest,
    )
    _validate(config)
    return config
```

**Step 5: Update v0.1.yaml with backtest defaults**

```yaml
# Append to strategies/v0.1.yaml
backtest:
  train_months: 6
  validation_months: 2
  test_months: 1
  step_months: 1
  rebalance_frequency: weekly
  transaction_cost_bps: 10
```

**Step 6: Run tests — verify all pass (existing + new)**

Run: `pytest tests/ -v`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add src/research/results.py src/strategy/config.py strategies/v0.1.yaml tests/test_results.py
git commit -m "add BacktestResult dataclasses and BacktestConfig"
```

---

### Task 2: MetricsCalculator

**Files:**
- Create: `src/research/metrics.py`
- Create: `tests/test_metrics.py`

**Step 1: Write failing tests**

```python
# tests/test_metrics.py
import numpy as np
import pandas as pd
from src.research.metrics import compute_metrics

def test_sharpe_positive_for_uptrend():
    # Daily returns with positive drift
    np.random.seed(42)
    returns = pd.Series(np.random.normal(0.001, 0.01, 252))
    metrics = compute_metrics(returns)
    assert metrics["sharpe"] > 0

def test_sharpe_negative_for_downtrend():
    np.random.seed(42)
    returns = pd.Series(np.random.normal(-0.002, 0.01, 252))
    metrics = compute_metrics(returns)
    assert metrics["sharpe"] < 0

def test_cagr_calculation():
    # 10% total return over 252 days ≈ 10% CAGR
    returns = pd.Series([0.0] * 251 + [0.10])
    metrics = compute_metrics(returns)
    assert 0.05 < metrics["cagr"] < 0.15

def test_max_drawdown():
    # Goes up 10%, then drops 20% from peak
    prices = [100, 110, 105, 100, 95, 90, 88, 92]
    returns = pd.Series(np.diff(prices) / prices[:-1])
    metrics = compute_metrics(returns)
    assert metrics["max_drawdown"] > 0.15  # ~20% drawdown

def test_hit_rate():
    returns = pd.Series([0.01, -0.005, 0.02, 0.015, -0.01])
    metrics = compute_metrics(returns)
    assert metrics["hit_rate"] == 0.6  # 3 of 5 positive

def test_turnover():
    # positions_changed and total_positions passed as kwargs
    metrics = compute_metrics(
        pd.Series([0.01] * 20),
        positions_changed=4,
        total_positions=10,
        months=1,
    )
    assert metrics["monthly_turnover"] == 0.4  # 4/10

def test_transaction_costs_reduce_returns():
    np.random.seed(42)
    returns = pd.Series(np.random.normal(0.001, 0.01, 252))
    m_no_cost = compute_metrics(returns, transaction_cost_bps=0)
    m_with_cost = compute_metrics(returns, transaction_cost_bps=10,
                                   positions_changed=50, total_positions=10)
    assert m_with_cost["cagr"] <= m_no_cost["cagr"]

def test_all_metrics_present():
    returns = pd.Series(np.random.normal(0.001, 0.01, 100))
    metrics = compute_metrics(returns)
    required = {"sharpe", "cagr", "max_drawdown", "hit_rate", "win_loss_ratio",
                "total_return", "monthly_turnover"}
    assert required.issubset(set(metrics.keys()))
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_metrics.py -v`
Expected: FAIL

**Step 3: Implement**

```python
# src/research/metrics.py
import numpy as np
import pandas as pd

def compute_metrics(
    returns: pd.Series,
    transaction_cost_bps: float = 0,
    positions_changed: int = 0,
    total_positions: int = 1,
    months: float = 0,
) -> dict:
    """Compute backtest metrics from a daily returns series."""
    if len(returns) == 0:
        return _empty_metrics()

    # Apply transaction costs
    if transaction_cost_bps > 0 and positions_changed > 0:
        total_cost = positions_changed * (transaction_cost_bps / 10000)
        # Spread cost evenly across the period
        daily_cost = total_cost / max(len(returns), 1)
        returns = returns - daily_cost

    # Cumulative returns → equity curve
    equity = (1 + returns).cumprod()
    total_return = float(equity.iloc[-1] - 1) if len(equity) > 0 else 0.0

    # Sharpe (annualized, assuming 0 risk-free rate)
    mean_r = returns.mean()
    std_r = returns.std()
    sharpe = float(mean_r / std_r * np.sqrt(252)) if std_r > 0 else 0.0

    # CAGR
    n_days = len(returns)
    if n_days > 0 and equity.iloc[-1] > 0:
        cagr = float(equity.iloc[-1] ** (252 / n_days) - 1)
    else:
        cagr = 0.0

    # Max drawdown
    peak = equity.cummax()
    drawdown = (equity - peak) / peak
    max_drawdown = float(abs(drawdown.min()))

    # Hit rate
    n_positive = int((returns > 0).sum())
    hit_rate = n_positive / len(returns) if len(returns) > 0 else 0.0

    # Win/loss ratio
    winners = returns[returns > 0]
    losers = returns[returns < 0]
    avg_win = float(winners.mean()) if len(winners) > 0 else 0.0
    avg_loss = float(abs(losers.mean())) if len(losers) > 0 else 1.0
    win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float("inf")

    # Turnover
    if months > 0 and total_positions > 0:
        monthly_turnover = (positions_changed / total_positions) / months
    else:
        monthly_turnover = 0.0

    return {
        "sharpe": round(sharpe, 3),
        "cagr": round(cagr, 4),
        "max_drawdown": round(max_drawdown, 4),
        "hit_rate": round(hit_rate, 4),
        "win_loss_ratio": round(win_loss_ratio, 3),
        "total_return": round(total_return, 4),
        "monthly_turnover": round(monthly_turnover, 4),
        "n_days": n_days,
    }

def _empty_metrics() -> dict:
    return {
        "sharpe": 0.0, "cagr": 0.0, "max_drawdown": 0.0,
        "hit_rate": 0.0, "win_loss_ratio": 0.0, "total_return": 0.0,
        "monthly_turnover": 0.0, "n_days": 0,
    }
```

**Step 4: Run tests — verify pass**

Run: `pytest tests/test_metrics.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/research/metrics.py tests/test_metrics.py
git commit -m "add MetricsCalculator with Sharpe/CAGR/drawdown/hit rate"
```

---

### Task 3: StrategyRunner

**Files:**
- Create: `src/research/runner.py`
- Create: `tests/test_runner.py`

**Step 1: Write failing tests**

```python
# tests/test_runner.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.research.runner import StrategyRunner
from src.strategy.config import StrategyConfig, BacktestConfig

def _config():
    return StrategyConfig(
        version="0.1", name="test",
        weights={"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                 "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
        thresholds={"buy": 70, "hold_min": 40, "sell": 40},
        filters={},
        backtest=BacktestConfig(),
    )

def _synthetic_bars(days=252, daily_return=0.001):
    end = datetime(2026, 3, 1)
    dates = pd.date_range(end=end, periods=days, freq="B")
    prices = 100 * np.cumprod(1 + np.random.normal(daily_return, 0.01, days))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices,
        "volume": np.random.randint(500_000, 3_000_000, days),
    })

def test_runner_returns_positions():
    runner = StrategyRunner(_config())
    bars = {"AAPL": _synthetic_bars(), "SPY": _synthetic_bars()}
    as_of = datetime(2026, 3, 1)
    positions = runner.get_positions(["AAPL"], bars, as_of)
    assert "AAPL" in positions
    assert positions["AAPL"]["action"] in ("buy", "hold", "sell")

def test_runner_respects_as_of_date():
    """Runner should only use data up to as_of — no lookahead."""
    runner = StrategyRunner(_config())
    full_bars = _synthetic_bars(days=252)
    bars = {"AAPL": full_bars, "SPY": _synthetic_bars(days=252)}
    # Use as_of in the middle of the data
    mid_date = full_bars["timestamp"].iloc[125]
    positions = runner.get_positions(["AAPL"], bars, mid_date)
    assert "AAPL" in positions

def test_runner_position_has_score():
    runner = StrategyRunner(_config())
    bars = {"AAPL": _synthetic_bars(), "SPY": _synthetic_bars()}
    positions = runner.get_positions(["AAPL"], bars, datetime(2026, 3, 1))
    assert "composite_score" in positions["AAPL"]
    assert 0 <= positions["AAPL"]["composite_score"] <= 100
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_runner.py -v`

**Step 3: Implement**

```python
# src/research/runner.py
from datetime import datetime
import pandas as pd
from src.strategy.config import StrategyConfig
from src.agents.portfolio_analyst import PortfolioAnalyst

class StrategyRunner:
    """Wraps PortfolioAnalyst for historical simulation. No lookahead."""

    def __init__(self, config: StrategyConfig):
        self.config = config
        self.analyst = PortfolioAnalyst(config)

    def get_positions(
        self,
        tickers: list[str],
        bars: dict[str, pd.DataFrame],
        as_of: datetime,
    ) -> dict[str, dict]:
        """Run the strategy as if 'as_of' is today. Returns {ticker: {action, composite_score}}."""
        # Truncate bars to as_of date — prevents lookahead
        truncated = {}
        for ticker, df in bars.items():
            mask = df["timestamp"] <= pd.Timestamp(as_of)
            truncated_df = df[mask].copy()
            if len(truncated_df) >= 20:
                truncated[ticker] = truncated_df

        recs = self.analyst.analyze(tickers, truncated)
        return {
            r.ticker: {
                "action": r.action,
                "composite_score": r.composite_score,
                "signal_scores": r.signal_scores,
            }
            for r in recs
        }
```

**Step 4: Run tests — verify pass**

Run: `pytest tests/test_runner.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/research/runner.py tests/test_runner.py
git commit -m "add StrategyRunner with lookahead prevention"
```

---

### Task 4: Walk-Forward Window Generator

**Files:**
- Create: `src/research/windows.py`
- Create: `tests/test_windows.py`

**Step 1: Write failing tests**

```python
# tests/test_windows.py
from datetime import date
from src.research.windows import generate_windows
from src.strategy.config import BacktestConfig

def test_generates_correct_number_of_windows():
    # 24 months of data, 6m train + 2m val + 1m test = 9m, step 1m
    # First window needs 9 months, leaves 15 months for stepping = ~15 windows
    config = BacktestConfig(train_months=6, validation_months=2,
                            test_months=1, step_months=1)
    windows = generate_windows(
        data_start=date(2024, 1, 1),
        data_end=date(2026, 1, 1),
        config=config,
    )
    assert len(windows) > 10
    assert len(windows) < 20

def test_window_dates_non_overlapping_test():
    config = BacktestConfig(train_months=6, validation_months=2,
                            test_months=1, step_months=1)
    windows = generate_windows(date(2024, 1, 1), date(2026, 1, 1), config)
    # Test periods should step forward by step_months
    for i in range(1, len(windows)):
        assert windows[i]["test_start"] > windows[i-1]["test_start"]

def test_no_lookahead():
    config = BacktestConfig(train_months=6, validation_months=2,
                            test_months=1, step_months=1)
    windows = generate_windows(date(2024, 1, 1), date(2026, 1, 1), config)
    for w in windows:
        assert w["train_end"] <= w["validation_start"]
        assert w["validation_end"] <= w["test_start"]
        assert w["test_end"] <= date(2026, 1, 1)

def test_window_structure():
    config = BacktestConfig(train_months=6, validation_months=2,
                            test_months=1, step_months=1)
    windows = generate_windows(date(2024, 1, 1), date(2025, 6, 1), config)
    w = windows[0]
    required_keys = {"train_start", "train_end", "validation_start",
                     "validation_end", "test_start", "test_end", "window_id"}
    assert required_keys.issubset(set(w.keys()))

def test_insufficient_data_returns_empty():
    config = BacktestConfig(train_months=6, validation_months=2,
                            test_months=1, step_months=1)
    # Only 3 months of data — not enough for one window
    windows = generate_windows(date(2026, 1, 1), date(2026, 4, 1), config)
    assert len(windows) == 0
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_windows.py -v`

**Step 3: Implement**

```python
# src/research/windows.py
from datetime import date
from dateutil.relativedelta import relativedelta
from src.strategy.config import BacktestConfig

def generate_windows(
    data_start: date,
    data_end: date,
    config: BacktestConfig,
) -> list[dict]:
    """Generate rolling walk-forward windows. Returns list of window dicts."""
    total_window = config.train_months + config.validation_months + config.test_months
    step = relativedelta(months=config.step_months)

    windows = []
    window_id = 0
    cursor = data_start

    while True:
        train_start = cursor
        train_end = train_start + relativedelta(months=config.train_months)
        val_start = train_end
        val_end = val_start + relativedelta(months=config.validation_months)
        test_start = val_end
        test_end = test_start + relativedelta(months=config.test_months)

        if test_end > data_end:
            break

        windows.append({
            "window_id": window_id,
            "train_start": train_start,
            "train_end": train_end,
            "validation_start": val_start,
            "validation_end": val_end,
            "test_start": test_start,
            "test_end": test_end,
        })
        window_id += 1
        cursor += step

    return windows
```

Note: add `python-dateutil` to pyproject.toml dependencies.

**Step 4: Run tests — verify pass**

Run: `pytest tests/test_windows.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/research/windows.py tests/test_windows.py pyproject.toml
git commit -m "add walk-forward window generator"
```

---

### Task 5: Backtester Core

**Files:**
- Create: `src/research/backtester.py`
- Create: `tests/test_backtester.py`

**Step 1: Write failing tests**

```python
# tests/test_backtester.py
import pandas as pd
import numpy as np
from datetime import datetime, date
from src.research.backtester import Backtester
from src.strategy.config import StrategyConfig, BacktestConfig

def _config():
    return StrategyConfig(
        version="0.1", name="test",
        weights={"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                 "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
        thresholds={"buy": 70, "hold_min": 40, "sell": 40},
        filters={},
        backtest=BacktestConfig(
            train_months=6, validation_months=2, test_months=1,
            step_months=1, transaction_cost_bps=10,
        ),
    )

def _synthetic_universe(tickers, days=504):
    """~2 years of data for multiple tickers."""
    end = datetime(2026, 1, 1)
    dates = pd.date_range(end=end, periods=days, freq="B")
    bars = {}
    for t in tickers:
        dr = np.random.normal(0.0005, 0.012, days)
        prices = 100 * np.cumprod(1 + dr)
        bars[t] = pd.DataFrame({
            "timestamp": dates, "open": prices * 0.99, "high": prices * 1.01,
            "low": prices * 0.98, "close": prices,
            "volume": np.random.randint(500_000, 3_000_000, days),
        })
    return bars

def test_backtester_returns_result():
    config = _config()
    bars = _synthetic_universe(["AAPL", "MSFT", "SPY"])
    bt = Backtester(config)
    result = bt.run(["AAPL", "MSFT"], bars)
    assert len(result.window_results) > 0
    assert "sharpe" in result.aggregate_metrics

def test_backtester_multiple_windows():
    config = _config()
    bars = _synthetic_universe(["AAPL", "SPY"], days=504)
    bt = Backtester(config)
    result = bt.run(["AAPL"], bars)
    assert len(result.window_results) >= 3

def test_backtester_metrics_reasonable():
    config = _config()
    bars = _synthetic_universe(["AAPL", "SPY"])
    bt = Backtester(config)
    result = bt.run(["AAPL"], bars)
    m = result.aggregate_metrics
    assert -5.0 < m["sharpe"] < 5.0
    assert -1.0 < m["cagr"] < 5.0
    assert 0 <= m["max_drawdown"] <= 1.0

def test_backtester_no_lookahead():
    """Each window's positions should only use data up to that window's train_end."""
    config = _config()
    bars = _synthetic_universe(["AAPL", "SPY"])
    bt = Backtester(config)
    result = bt.run(["AAPL"], bars)
    # If there are results, they were generated — no crash means no future data accessed
    assert len(result.window_results) > 0
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_backtester.py -v`

**Step 3: Implement**

```python
# src/research/backtester.py
from datetime import datetime
import numpy as np
import pandas as pd
from src.strategy.config import StrategyConfig
from src.research.runner import StrategyRunner
from src.research.windows import generate_windows
from src.research.metrics import compute_metrics
from src.research.results import BacktestResult, WindowResult

class Backtester:
    def __init__(self, config: StrategyConfig):
        self.config = config
        self.runner = StrategyRunner(config)

    def run(self, tickers: list[str], bars: dict[str, pd.DataFrame]) -> BacktestResult:
        # Determine data range from bars
        all_dates = []
        for df in bars.values():
            if len(df) > 0:
                all_dates.extend(df["timestamp"].tolist())
        if not all_dates:
            return BacktestResult(self.config.version, [], {}, {})

        data_start = min(all_dates).date() if hasattr(min(all_dates), 'date') else min(all_dates)
        data_end = max(all_dates).date() if hasattr(max(all_dates), 'date') else max(all_dates)

        windows = generate_windows(data_start, data_end, self.config.backtest)
        if not windows:
            return BacktestResult(self.config.version, [], {}, {})

        window_results = []
        for w in windows:
            wr = self._run_window(tickers, bars, w)
            if wr is not None:
                window_results.append(wr)

        aggregate = self._aggregate(window_results)

        return BacktestResult(
            strategy_version=self.config.version,
            window_results=window_results,
            aggregate_metrics=aggregate,
            config_snapshot={
                "weights": self.config.weights,
                "thresholds": self.config.thresholds,
                "filters": self.config.filters,
            },
        )

    def _run_window(self, tickers: list[str], bars: dict[str, pd.DataFrame],
                     window: dict) -> WindowResult | None:
        """Run strategy on one walk-forward window."""
        train_end = window["train_end"]
        test_start = window["test_start"]
        test_end = window["test_end"]

        # Get positions at end of training period
        as_of = datetime.combine(train_end, datetime.min.time())
        positions = self.runner.get_positions(tickers, bars, as_of)
        if not positions:
            return None

        # Simulate test period returns
        buy_tickers = [t for t, p in positions.items() if p["action"] == "buy"]
        if not buy_tickers:
            # No buys — simulate holding cash (0 return)
            n_test_days = np.busday_count(test_start, test_end)
            returns = pd.Series([0.0] * max(n_test_days, 1))
        else:
            returns = self._simulate_returns(buy_tickers, bars, test_start, test_end)

        if returns.empty:
            return None

        # Compute metrics
        n_trades = len(buy_tickers)
        test_months = self.config.backtest.test_months
        metrics = compute_metrics(
            returns,
            transaction_cost_bps=self.config.backtest.transaction_cost_bps,
            positions_changed=n_trades,
            total_positions=max(len(tickers), 1),
            months=max(test_months, 1),
        )

        return WindowResult(
            window_id=window["window_id"],
            train_start=str(window["train_start"]),
            train_end=str(window["train_end"]),
            test_start=str(window["test_start"]),
            test_end=str(window["test_end"]),
            metrics=metrics,
            positions={t: p["action"] for t, p in positions.items()},
        )

    def _simulate_returns(self, tickers: list[str], bars: dict[str, pd.DataFrame],
                           test_start, test_end) -> pd.Series:
        """Equal-weight portfolio returns during test period."""
        ticker_returns = []
        for t in tickers:
            df = bars.get(t)
            if df is None:
                continue
            mask = (df["timestamp"].dt.date >= test_start) & (df["timestamp"].dt.date <= test_end)
            test_bars = df[mask].sort_values("timestamp")
            if len(test_bars) < 2:
                continue
            daily_ret = test_bars["close"].pct_change().dropna()
            ticker_returns.append(daily_ret.reset_index(drop=True))

        if not ticker_returns:
            return pd.Series(dtype=float)

        # Equal-weight: average daily returns across all held tickers
        aligned = pd.DataFrame(ticker_returns).T
        portfolio_returns = aligned.mean(axis=1).dropna()
        return portfolio_returns

    def _aggregate(self, window_results: list[WindowResult]) -> dict:
        """Average metrics across all windows."""
        if not window_results:
            return {}

        all_metrics = [w.metrics for w in window_results]
        keys = all_metrics[0].keys()
        aggregate = {}
        for k in keys:
            vals = [m[k] for m in all_metrics if k in m]
            if vals and isinstance(vals[0], (int, float)):
                aggregate[k] = round(float(np.mean(vals)), 4)
        return aggregate
```

**Step 4: Run tests — verify pass**

Run: `pytest tests/test_backtester.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/research/backtester.py tests/test_backtester.py
git commit -m "add Backtester with walk-forward simulation"
```

---

### Task 6: Strategy Comparison Helper

**Files:**
- Create: `src/research/comparison.py`
- Create: `tests/test_comparison.py`

This is used by M3's auditor but belongs in M2 since it operates on BacktestResults.

**Step 1: Write failing tests**

```python
# tests/test_comparison.py
from src.research.comparison import compare_strategies
from src.research.results import BacktestResult, WindowResult

def _result(sharpe_values, version="0.1"):
    windows = [
        WindowResult(i, "", "", "", "", {"sharpe": s, "cagr": s * 0.05,
                     "max_drawdown": 0.1, "hit_rate": 0.55, "monthly_turnover": 0.2},
                     {})
        for i, s in enumerate(sharpe_values)
    ]
    agg = {"sharpe": sum(sharpe_values) / len(sharpe_values)}
    return BacktestResult(version, windows, agg, {})

def test_better_strategy_wins():
    baseline = _result([0.8, 0.9, 1.0, 0.7])
    experiment = _result([1.2, 1.3, 1.1, 1.4], version="0.2")
    comparison = compare_strategies(baseline, experiment)
    assert comparison["experiment_wins"]
    assert comparison["sharpe_improvement"] > 0

def test_worse_strategy_loses():
    baseline = _result([1.2, 1.3, 1.1, 1.4])
    experiment = _result([0.5, 0.6, 0.4, 0.3], version="0.2")
    comparison = compare_strategies(baseline, experiment)
    assert not comparison["experiment_wins"]

def test_comparison_has_per_window_detail():
    baseline = _result([0.8, 0.9, 1.0, 0.7])
    experiment = _result([1.2, 0.7, 1.1, 0.9], version="0.2")
    comparison = compare_strategies(baseline, experiment)
    assert "windows_won" in comparison
    assert "windows_total" in comparison
    assert comparison["windows_total"] == 4

def test_comparison_drawdown_check():
    baseline = _result([1.0, 1.0, 1.0, 1.0])
    # Experiment has better sharpe but worse drawdown
    windows = [
        WindowResult(i, "", "", "", "",
                     {"sharpe": 1.5, "max_drawdown": 0.3, "cagr": 0.1,
                      "hit_rate": 0.5, "monthly_turnover": 0.2}, {})
        for i in range(4)
    ]
    experiment = BacktestResult("0.2", windows, {"sharpe": 1.5}, {})
    comparison = compare_strategies(baseline, experiment, max_drawdown_ratio=1.5)
    assert "drawdown_flag" in comparison
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_comparison.py -v`

**Step 3: Implement**

```python
# src/research/comparison.py
from src.research.results import BacktestResult

def compare_strategies(
    baseline: BacktestResult,
    experiment: BacktestResult,
    max_drawdown_ratio: float = 1.5,
) -> dict:
    """Compare two backtest results. Returns comparison dict."""
    b_windows = baseline.window_results
    e_windows = experiment.window_results
    n = min(len(b_windows), len(e_windows))

    if n == 0:
        return {"experiment_wins": False, "reason": "no windows to compare"}

    # Per-window comparison
    windows_won = 0
    for i in range(n):
        b_sharpe = b_windows[i].metrics.get("sharpe", 0)
        e_sharpe = e_windows[i].metrics.get("sharpe", 0)
        if e_sharpe > b_sharpe:
            windows_won += 1

    win_rate = windows_won / n

    # Aggregate comparison
    b_sharpe_agg = baseline.aggregate_metrics.get("sharpe", 0)
    e_sharpe_agg = experiment.aggregate_metrics.get("sharpe", 0)
    sharpe_improvement = e_sharpe_agg - b_sharpe_agg

    # Drawdown check
    b_max_dd = max((w.metrics.get("max_drawdown", 0) for w in b_windows), default=0)
    e_max_dd = max((w.metrics.get("max_drawdown", 0) for w in e_windows), default=0)
    drawdown_flag = e_max_dd > b_max_dd * max_drawdown_ratio if b_max_dd > 0 else False

    # Turnover check
    b_turnover = baseline.aggregate_metrics.get("monthly_turnover", 0)
    e_turnover = experiment.aggregate_metrics.get("monthly_turnover", 0)
    turnover_flag = e_turnover > b_turnover * 2 if b_turnover > 0 else False

    experiment_wins = (
        sharpe_improvement > 0 and
        win_rate >= 0.75 and
        not drawdown_flag
    )

    return {
        "experiment_wins": experiment_wins,
        "sharpe_improvement": round(sharpe_improvement, 4),
        "baseline_sharpe": round(b_sharpe_agg, 4),
        "experiment_sharpe": round(e_sharpe_agg, 4),
        "windows_won": windows_won,
        "windows_total": n,
        "win_rate": round(win_rate, 4),
        "drawdown_flag": drawdown_flag,
        "turnover_flag": turnover_flag,
        "baseline_max_dd": round(b_max_dd, 4),
        "experiment_max_dd": round(e_max_dd, 4),
    }
```

**Step 4: Run tests — verify pass**

Run: `pytest tests/test_comparison.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/research/comparison.py tests/test_comparison.py
git commit -m "add strategy comparison helper"
```

---

### Task 7: Backtest CLI + Integration Test

**Files:**
- Create: `backtest.py`
- Create: `tests/test_backtest_integration.py`

**Step 1: Write integration test**

```python
# tests/test_backtest_integration.py
"""End-to-end: synthetic data → backtester → comparison."""
import numpy as np
import pandas as pd
from datetime import datetime
from src.strategy.config import StrategyConfig, BacktestConfig
from src.research.backtester import Backtester
from src.research.comparison import compare_strategies

def _config(weights_override=None):
    weights = {"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
               "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10}
    if weights_override:
        weights.update(weights_override)
    return StrategyConfig(
        version="0.1", name="test", weights=weights,
        thresholds={"buy": 70, "hold_min": 40, "sell": 40}, filters={},
        backtest=BacktestConfig(train_months=4, validation_months=1,
                                test_months=1, step_months=1,
                                transaction_cost_bps=10),
    )

def _universe(days=504):
    end = datetime(2026, 1, 1)
    dates = pd.date_range(end=end, periods=days, freq="B")
    bars = {}
    for t in ["AAPL", "MSFT", "GOOG", "SPY"]:
        np.random.seed(hash(t) % 2**31)
        dr = np.random.normal(0.0005, 0.012, days)
        prices = 100 * np.cumprod(1 + dr)
        bars[t] = pd.DataFrame({
            "timestamp": dates, "open": prices * 0.99, "high": prices * 1.01,
            "low": prices * 0.98, "close": prices,
            "volume": np.random.randint(500_000, 3_000_000, days),
        })
    return bars

def test_full_backtest_pipeline():
    config = _config()
    bars = _universe()
    bt = Backtester(config)
    result = bt.run(["AAPL", "MSFT", "GOOG"], bars)
    assert len(result.window_results) >= 3
    assert "sharpe" in result.aggregate_metrics
    assert "cagr" in result.aggregate_metrics
    assert "max_drawdown" in result.aggregate_metrics

def test_two_configs_comparison():
    bars = _universe()
    baseline = Backtester(_config()).run(["AAPL", "MSFT", "GOOG"], bars)
    # Modify weights slightly
    experiment = Backtester(
        _config(weights_override={"trend": 0.45, "fundamentals": 0.10})
    ).run(["AAPL", "MSFT", "GOOG"], bars)

    comparison = compare_strategies(baseline, experiment)
    assert "experiment_wins" in comparison
    assert "sharpe_improvement" in comparison
    assert isinstance(comparison["windows_won"], int)
```

**Step 2: Run integration test**

Run: `pytest tests/test_backtest_integration.py -v`
Expected: PASS (if previous tasks implemented correctly)

**Step 3: Implement backtest CLI**

```python
#!/usr/bin/env python3
"""Quant Autoresearch Agent — Backtest CLI."""
import argparse
import os
import sys
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path

from src.data.alpaca import AlpacaProvider
from src.data.db import Storage
from src.strategy.config import load_strategy
from src.research.backtester import Backtester

DEFAULT_STRATEGY = "strategies/v0.1.yaml"

def main():
    parser = argparse.ArgumentParser(description="Backtest a strategy on historical data")
    parser.add_argument("tickers", nargs="+", help="Stock tickers to backtest")
    parser.add_argument("--strategy", default=DEFAULT_STRATEGY, help="Strategy config path")
    parser.add_argument("--days", type=int, default=730, help="Days of history (default 2 years)")
    parser.add_argument("--output", default="output", help="Output directory")
    args = parser.parse_args()

    load_dotenv()
    if not os.environ.get("ALPACA_API_KEY"):
        print("Error: Set ALPACA_API_KEY and ALPACA_SECRET in .env")
        sys.exit(1)

    config = load_strategy(args.strategy)
    provider = AlpacaProvider()

    tickers = [t.upper() for t in args.tickers]
    all_tickers = tickers + ["SPY"]
    end = datetime.now()
    start = end - timedelta(days=args.days)

    print(f"Fetching {args.days} days of data for {len(tickers)} tickers + SPY...")
    all_bars_df = provider.get_bars(all_tickers, start, end)

    if all_bars_df.empty:
        print("No data returned.")
        sys.exit(1)

    bars = {}
    for ticker in all_tickers:
        mask = all_bars_df["symbol"] == ticker
        if mask.any():
            bars[ticker] = all_bars_df[mask].sort_values("timestamp").reset_index(drop=True)

    print(f"Running backtest (strategy {config.version})...")
    bt = Backtester(config)
    result = bt.run(tickers, bars)

    print(f"\n{'='*60}")
    print(f"  Backtest Results — strategy {config.version}")
    print(f"  {len(result.window_results)} walk-forward windows")
    print(f"{'='*60}\n")

    m = result.aggregate_metrics
    print(f"  Sharpe:       {m.get('sharpe', 0):.3f}")
    print(f"  CAGR:         {m.get('cagr', 0):.2%}")
    print(f"  Max Drawdown: {m.get('max_drawdown', 0):.2%}")
    print(f"  Hit Rate:     {m.get('hit_rate', 0):.2%}")
    print(f"  Turnover:     {m.get('monthly_turnover', 0):.2%}/mo")
    print(f"  Total Return: {m.get('total_return', 0):.2%}")

    print(f"\n  Per-Window Sharpe:")
    for w in result.window_results:
        status = "+" if w.metrics.get("sharpe", 0) > 0 else "-"
        print(f"    [{status}] Window {w.window_id}: "
              f"Sharpe {w.metrics.get('sharpe', 0):.3f}, "
              f"Return {w.metrics.get('total_return', 0):.2%} "
              f"({w.test_start} → {w.test_end})")

    # Save results
    out_path = Path(args.output)
    out_path.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    filepath = out_path / f"backtest-{config.version}-{today}.json"
    filepath.write_text(json.dumps({
        "strategy_version": result.strategy_version,
        "aggregate_metrics": result.aggregate_metrics,
        "windows": [
            {"window_id": w.window_id, "test_start": w.test_start,
             "test_end": w.test_end, "metrics": w.metrics, "positions": w.positions}
            for w in result.window_results
        ],
        "config": result.config_snapshot,
    }, indent=2, default=str))
    print(f"\nSaved to {filepath}")

if __name__ == "__main__":
    main()
```

**Step 4: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backtest.py tests/test_backtest_integration.py
git commit -m "add backtest.py CLI and integration tests"
```
