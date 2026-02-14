# src/agents/signals/volatility.py
import numpy as np
import pandas as pd
from datetime import datetime
from src.agents.base import BaseSignal
from src.models.types import SignalScore

class VolatilitySignal(BaseSignal):
    name = "volatility"

    def score(self, ticker: str, bars: pd.DataFrame, benchmark_bars: pd.DataFrame | None = None) -> SignalScore:
        close = bars["close"].values
        if len(close) < 21:
            return SignalScore(ticker=ticker, signal=self.name, score=50.0,
                               confidence=0.1, components={"insufficient_data": True})

        components = self._compute(bars)
        composite = (
            0.35 * components["volatility_score"] +
            0.35 * components["drawdown_score"] +
            0.30 * components["distance_from_high"]
        )
        return SignalScore(
            ticker=ticker, signal=self.name,
            score=float(np.clip(composite, 0, 100)),
            confidence=min(len(close) / 126, 1.0),
            components=components, timestamp=datetime.now(),
        )

    def _compute(self, df: pd.DataFrame) -> dict:
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values

        # Annualized volatility (20d), lower = better score
        returns = np.diff(np.log(close[-21:]))
        annual_vol = float(np.std(returns) * np.sqrt(252) * 100)
        volatility_score = float(np.clip(100 - annual_vol * 2, 0, 100))

        # Max drawdown (6 months), smaller = better
        lookback = min(len(close), 126)
        recent = close[-lookback:]
        peak = np.maximum.accumulate(recent)
        drawdowns = (recent - peak) / peak
        max_dd = abs(float(np.min(drawdowns))) * 100
        drawdown_score = float(np.clip(100 - max_dd * 3, 0, 100))

        # Distance from 52-week high, closer = better
        high_52w = float(np.max(high[-min(len(high), 252):]))
        dist_pct = (high_52w - close[-1]) / high_52w * 100
        distance_from_high = float(np.clip(100 - dist_pct * 3, 0, 100))

        # Risk params
        prev_close = close[-21:-1]
        h20, l20 = high[-20:], low[-20:]
        tr = np.maximum(h20 - l20, np.maximum(np.abs(h20 - prev_close), np.abs(l20 - prev_close)))
        atr = float(np.mean(tr))
        stop_loss = round(float(close[-1] - 2 * atr), 2)
        max_position_pct = round(float(np.clip(20 - annual_vol * 0.3, 2, 15)), 1)

        return {
            "volatility_score": round(volatility_score, 1),
            "drawdown_score": round(drawdown_score, 1),
            "distance_from_high": round(distance_from_high, 1),
            "annual_vol_pct": round(annual_vol, 1),
            "max_drawdown_pct": round(max_dd, 1),
            "stop_loss": stop_loss,
            "max_position_pct": max_position_pct,
        }

    def explain(self, score: SignalScore) -> str:
        c = score.components
        if c.get("insufficient_data"):
            return f"{score.ticker}: insufficient data for volatility analysis"
        parts = []
        if c["volatility_score"] > 70: parts.append("low volatility")
        elif c["volatility_score"] < 30: parts.append(f"high vol ({c['annual_vol_pct']:.0f}% ann)")
        if c["drawdown_score"] < 40: parts.append(f"drawdown {c['max_drawdown_pct']:.0f}%")
        if c["distance_from_high"] > 80: parts.append("near 52w highs")
        risk = f"Stop ${c['stop_loss']}, max {c['max_position_pct']}%"
        summary = ", ".join(parts) if parts else "moderate vol profile"
        return f"{score.ticker} vol ({score.score:.0f}): {summary}. {risk}"
