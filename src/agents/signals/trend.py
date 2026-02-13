# src/agents/signals/trend.py
import numpy as np
import pandas as pd
from datetime import datetime
from src.agents.base import BaseSignal
from src.models.types import SignalScore

class TrendSignal(BaseSignal):
    name = "trend"

    def score(self, ticker: str, bars: pd.DataFrame, benchmark_bars: pd.DataFrame | None = None) -> SignalScore:
        close = bars["close"].values
        if len(close) < 50:
            return SignalScore(ticker=ticker, signal=self.name, score=50.0,
                               confidence=0.1, components={"insufficient_data": True})

        components = self._compute(bars)
        composite = (
            0.35 * components["momentum"] +
            0.30 * components["sma_structure"] +
            0.20 * components["vol_contraction"] +
            0.15 * components["volume_confirm"]
        )
        return SignalScore(
            ticker=ticker, signal=self.name,
            score=float(np.clip(composite, 0, 100)),
            confidence=min(len(close) / 252, 1.0),
            components=components, timestamp=datetime.now(),
        )

    def _compute(self, df: pd.DataFrame) -> dict:
        close = df["close"].values

        # Momentum: avg of 3m/6m/12m returns, centered at 50
        mom_3m = (close[-1] / close[-63] - 1) if len(close) >= 63 else 0
        mom_6m = (close[-1] / close[-126] - 1) if len(close) >= 126 else 0
        mom_12m = (close[-1] / close[-252] - 1) if len(close) >= 252 else mom_6m
        raw_mom = (mom_3m + mom_6m + mom_12m) / 3
        momentum = float(np.clip(50 + raw_mom * 200, 0, 100))

        # SMA structure: price vs 20/50/200 SMA, SMA ordering
        sma20 = np.mean(close[-20:])
        sma50 = np.mean(close[-50:]) if len(close) >= 50 else close[-1]
        sma200 = np.mean(close[-200:]) if len(close) >= 200 else sma50
        checks = [
            close[-1] > sma20,
            close[-1] > sma50,
            close[-1] > sma200,
            sma20 > sma50,
            sma50 > sma200,
        ]
        sma_structure = sum(checks) / len(checks) * 100

        # Volatility contraction: lower ATR% = tighter = better
        if len(df) >= 21:
            high = df["high"].values[-20:]
            low = df["low"].values[-20:]
            prev_close = close[-21:-1]
            tr = np.maximum(high - low, np.maximum(
                np.abs(high - prev_close), np.abs(low - prev_close)
            ))
            atr_pct = np.mean(tr) / close[-1] * 100
            vol_contraction = float(np.clip(100 - atr_pct * 20, 0, 100))
        else:
            vol_contraction = 50.0

        # Volume confirmation: up-day vol vs down-day vol ratio
        if len(df) >= 20:
            recent = df.tail(20)
            up_mask = recent["close"].values > recent["open"].values
            up_vol = recent.loc[up_mask, "volume"].mean() if up_mask.any() else 1
            down_vol = recent.loc[~up_mask, "volume"].mean() if (~up_mask).any() else 1
            ratio = up_vol / max(down_vol, 1)
            volume_confirm = float(np.clip(ratio / 2 * 100, 0, 100))
        else:
            volume_confirm = 50.0

        return {
            "momentum": round(momentum, 1),
            "sma_structure": round(float(sma_structure), 1),
            "vol_contraction": round(vol_contraction, 1),
            "volume_confirm": round(volume_confirm, 1),
        }

    def explain(self, score: SignalScore) -> str:
        c = score.components
        if c.get("insufficient_data"):
            return f"{score.ticker}: insufficient data for trend analysis"
        parts = []
        if c["momentum"] > 65: parts.append("strong momentum")
        elif c["momentum"] < 35: parts.append("weak momentum")
        if c["sma_structure"] >= 80: parts.append("above all key SMAs")
        elif c["sma_structure"] <= 40: parts.append("below key SMAs")
        if c["vol_contraction"] > 70: parts.append("tight volatility")
        if c["volume_confirm"] > 65: parts.append("volume confirming")
        summary = ", ".join(parts) if parts else "mixed trend signals"
        return f"{score.ticker} trend ({score.score:.0f}): {summary}"
