# src/research/paper_trader.py
import logging
from datetime import date, datetime
import pandas as pd
from src.data.db import Storage
from src.research.runner import StrategyRunner

logger = logging.getLogger(__name__)


class PaperTrader:
    def __init__(
        self,
        db: Storage,
        experiment_id: str,
        tickers: list[str],
        bars: dict[str, pd.DataFrame],
        baseline_runner: StrategyRunner,
        experiment_runner: StrategyRunner,
    ):
        self.db = db
        self.experiment_id = experiment_id
        self.tickers = tickers
        self.bars = bars
        self.baseline_runner = baseline_runner
        self.experiment_runner = experiment_runner

    def record_day(self, trade_date: date) -> dict | None:
        """Record one day of shadow portfolio tracking."""
        as_of = datetime.combine(trade_date, datetime.min.time())

        baseline_pos = self.baseline_runner.get_positions(self.tickers, self.bars, as_of)
        experiment_pos = self.experiment_runner.get_positions(self.tickers, self.bars, as_of)

        baseline_buys = [t for t, p in baseline_pos.items() if p["action"] == "buy"]
        experiment_buys = [t for t, p in experiment_pos.items() if p["action"] == "buy"]

        baseline_ret = self._daily_return(baseline_buys, trade_date)
        experiment_ret = self._daily_return(experiment_buys, trade_date)

        # Get previous cumulative
        prev_trades = self.db.get_paper_trades(self.experiment_id)
        if prev_trades:
            prev_b_cum = prev_trades[-1]["baseline_cumulative"]
            prev_e_cum = prev_trades[-1]["experiment_cumulative"]
        else:
            prev_b_cum = 0.0
            prev_e_cum = 0.0

        b_cum = prev_b_cum + baseline_ret
        e_cum = prev_e_cum + experiment_ret

        self.db.store_paper_trade(
            experiment_id=self.experiment_id,
            trade_date=trade_date,
            baseline_positions={t: p["action"] for t, p in baseline_pos.items()},
            experiment_positions={t: p["action"] for t, p in experiment_pos.items()},
            baseline_return=round(baseline_ret, 6),
            experiment_return=round(experiment_ret, 6),
            baseline_cumulative=round(b_cum, 6),
            experiment_cumulative=round(e_cum, 6),
        )

        return {
            "baseline_return": baseline_ret,
            "experiment_return": experiment_ret,
            "baseline_cumulative": b_cum,
            "experiment_cumulative": e_cum,
        }

    def _daily_return(self, buy_tickers: list[str], trade_date: date) -> float:
        """Equal-weight daily return for given tickers on trade_date."""
        if not buy_tickers:
            return 0.0

        returns = []
        for t in buy_tickers:
            df = self.bars.get(t)
            if df is None:
                continue
            mask = df["timestamp"].dt.date <= trade_date
            recent = df[mask].sort_values("timestamp").tail(2)
            if len(recent) < 2:
                continue
            prev_close = recent.iloc[-2]["close"]
            curr_close = recent.iloc[-1]["close"]
            if prev_close > 0:
                returns.append((curr_close - prev_close) / prev_close)

        if not returns:
            return 0.0
        return sum(returns) / len(returns)

    @staticmethod
    def evaluate_gate(
        experiment_id: str,
        db: Storage,
        max_underperformance: float = 0.01,
    ) -> dict:
        """Evaluate the paper trading gate after N days."""
        trades = db.get_paper_trades(experiment_id)
        if not trades:
            return {"passed": False, "reason": "No paper trades recorded"}

        last = trades[-1]
        e_cum = last["experiment_cumulative"]
        b_cum = last["baseline_cumulative"]
        n_days = len(trades)

        # Directional consistency (secondary)
        days_won = sum(1 for t in trades if t["experiment_return"] > t["baseline_return"])
        consistency = days_won / n_days if n_days > 0 else 0

        # Primary gate: non-negative AND not underperforming by >threshold
        if e_cum < 0:
            return {
                "passed": False,
                "reason": f"Negative return: experiment cumulative = {e_cum:.4f}",
                "experiment_cumulative": e_cum,
                "baseline_cumulative": b_cum,
                "beat_baseline": e_cum > b_cum,
                "directional_consistency": consistency,
                "days": n_days,
            }

        underperformance = b_cum - e_cum
        if underperformance > max_underperformance:
            return {
                "passed": False,
                "reason": f"Underperformance vs baseline: {underperformance:.4f} > {max_underperformance}",
                "experiment_cumulative": e_cum,
                "baseline_cumulative": b_cum,
                "beat_baseline": False,
                "directional_consistency": consistency,
                "days": n_days,
            }

        return {
            "passed": True,
            "reason": "Paper trading gate passed",
            "experiment_cumulative": e_cum,
            "baseline_cumulative": b_cum,
            "beat_baseline": e_cum > b_cum,
            "directional_consistency": consistency,
            "days": n_days,
        }
