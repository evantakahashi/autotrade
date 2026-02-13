# src/agents/base.py
from abc import ABC, abstractmethod
import pandas as pd
from src.models.types import SignalScore

class BaseSignal(ABC):
    """All scoring signals implement this."""
    name: str

    @abstractmethod
    def score(self, ticker: str, bars: pd.DataFrame, benchmark_bars: pd.DataFrame | None = None) -> SignalScore:
        """Score a single ticker. bars = that ticker's OHLCV DataFrame."""

    @abstractmethod
    def explain(self, score: SignalScore) -> str:
        """Human-readable explanation."""
