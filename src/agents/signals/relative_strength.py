# src/agents/signals/relative_strength.py
import numpy as np
import pandas as pd
from datetime import datetime
from src.agents.base import BaseSignal
from src.models.types import SignalScore

class RelativeStrengthSignal(BaseSignal):
    name = "relative_strength"

    def score(self, ticker: str, bars: pd.DataFrame, benchmark_bars: pd.DataFrame | None = None) -> SignalScore:
        if benchmark_bars is None or len(bars) < 63:
            return SignalScore(ticker=ticker, signal=self.name, score=50.0,
                               confidence=0.0, components={"no_benchmark": True})

        close = bars["close"].values
        bench = benchmark_bars["close"].values
        min_len = min(len(close), len(bench))
        close = close[-min_len:]
        bench = bench[-min_len:]

        components = {}
        periods = {"rs_3m": 63, "rs_6m": 126, "rs_12m": 252}
        rs_scores = []
        for label, lookback in periods.items():
            if min_len >= lookback:
                stock_ret = close[-1] / close[-lookback] - 1
                bench_ret = bench[-1] / bench[-lookback] - 1
                excess = stock_ret - bench_ret
                scaled = float(np.clip(50 + excess * 200, 0, 100))
            else:
                scaled = 50.0
            components[label] = round(scaled, 1)
            rs_scores.append(scaled)

        composite = float(np.clip(np.mean(rs_scores), 0, 100))
        return SignalScore(
            ticker=ticker, signal=self.name, score=composite,
            confidence=min(min_len / 252, 1.0),
            components=components, timestamp=datetime.now(),
        )

    def explain(self, score: SignalScore) -> str:
        c = score.components
        if c.get("no_benchmark"):
            return f"{score.ticker}: no benchmark data for relative strength"
        if score.score > 65:
            return f"{score.ticker} RS ({score.score:.0f}): outperforming benchmark"
        elif score.score < 35:
            return f"{score.ticker} RS ({score.score:.0f}): underperforming benchmark"
        return f"{score.ticker} RS ({score.score:.0f}): in line with benchmark"
