# src/data/provider.py
from abc import ABC, abstractmethod
from datetime import datetime
import pandas as pd
from src.models.types import Stock, NewsArticle

class DataProvider(ABC):
    @abstractmethod
    def get_assets(self) -> list[Stock]:
        """All tradable US equities."""

    @abstractmethod
    def get_bars(self, tickers: list[str], start: datetime, end: datetime) -> pd.DataFrame:
        """OHLCV bars. Returns DataFrame with columns: symbol, timestamp, open, high, low, close, volume."""

    @abstractmethod
    def get_news(self, tickers: list[str], start: datetime, end: datetime) -> list[NewsArticle]:
        """News articles for given tickers."""
