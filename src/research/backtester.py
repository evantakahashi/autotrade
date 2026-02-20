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
            # No buys -- simulate holding cash (0 return)
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
