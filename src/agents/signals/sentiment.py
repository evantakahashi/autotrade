# src/agents/signals/sentiment.py
import pandas as pd
from datetime import datetime
from src.agents.base import BaseSignal
from src.models.types import SignalScore

class SentimentSignal(BaseSignal):
    name = "sentiment"

    def score(self, ticker: str, bars: pd.DataFrame, benchmark_bars: pd.DataFrame | None = None) -> SignalScore:
        return SignalScore(
            ticker=ticker, signal=self.name, score=50.0, confidence=0.0,
            components={"status": "stubbed"}, timestamp=datetime.now(),
        )

    def explain(self, score: SignalScore) -> str:
        return f"{score.ticker} sentiment: stubbed — data not yet available"
