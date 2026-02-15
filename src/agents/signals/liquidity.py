# src/agents/signals/liquidity.py
import numpy as np
import pandas as pd
from datetime import datetime
from src.agents.base import BaseSignal
from src.models.types import SignalScore

class LiquiditySignal(BaseSignal):
    name = "liquidity"

    def score(self, ticker: str, bars: pd.DataFrame, benchmark_bars: pd.DataFrame | None = None) -> SignalScore:
        if len(bars) < 20:
            return SignalScore(ticker=ticker, signal=self.name, score=50.0,
                               confidence=0.1, components={"insufficient_data": True})

        close = bars["close"].values[-20:]
        volume = bars["volume"].values[-20:]
        avg_dollar_vol = float(np.mean(close * volume))
        avg_share_vol = float(np.mean(volume))

        # Score: log scale. $50M+/day = 100, $1M = ~60, $100K = ~30
        dollar_score = float(np.clip(np.log10(max(avg_dollar_vol, 1)) / 8 * 100, 0, 100))

        # Volume consistency: std/mean of daily volume (lower = more consistent)
        vol_cv = float(np.std(volume) / max(np.mean(volume), 1))
        consistency = float(np.clip(100 - vol_cv * 100, 0, 100))

        composite = 0.7 * dollar_score + 0.3 * consistency

        return SignalScore(
            ticker=ticker, signal=self.name,
            score=float(np.clip(composite, 0, 100)),
            confidence=0.9,
            components={
                "avg_dollar_volume": round(avg_dollar_vol, 0),
                "avg_share_volume": round(avg_share_vol, 0),
                "dollar_score": round(dollar_score, 1),
                "consistency": round(consistency, 1),
            },
            timestamp=datetime.now(),
        )

    def explain(self, score: SignalScore) -> str:
        c = score.components
        if c.get("insufficient_data"):
            return f"{score.ticker}: insufficient data for liquidity analysis"
        adv = c["avg_dollar_volume"]
        if adv > 50_000_000:
            liq_desc = "very liquid"
        elif adv > 5_000_000:
            liq_desc = "liquid"
        elif adv > 500_000:
            liq_desc = "moderate liquidity"
        else:
            liq_desc = "low liquidity — caution"
        return f"{score.ticker} liquidity ({score.score:.0f}): {liq_desc} (${adv/1e6:.1f}M avg daily)"
