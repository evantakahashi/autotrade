# src/data/alpaca.py
import os
import pandas as pd
from datetime import datetime
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass, AssetStatus
from src.data.provider import DataProvider
from src.models.types import Stock, NewsArticle

class AlpacaProvider(DataProvider):
    def __init__(self, api_key: str | None = None, secret_key: str | None = None):
        self._api_key = api_key or os.environ["ALPACA_API_KEY"]
        self._secret_key = secret_key or os.environ["ALPACA_SECRET"]
        self._data_client = StockHistoricalDataClient(self._api_key, self._secret_key)
        self._trading_client = TradingClient(self._api_key, self._secret_key)

    def get_assets(self) -> list[Stock]:
        request = GetAssetsRequest(asset_class=AssetClass.US_EQUITY, status=AssetStatus.ACTIVE)
        raw = self._trading_client.get_all_assets(request)
        return [
            Stock(ticker=a.symbol, name=a.name or "", exchange=str(a.exchange))
            for a in raw if a.tradable
        ]

    def get_bars(self, tickers: list[str], start: datetime, end: datetime) -> pd.DataFrame:
        all_frames = []
        # Alpaca limits ~200 symbols per request
        for i in range(0, len(tickers), 200):
            batch = tickers[i:i+200]
            request = StockBarsRequest(
                symbol_or_symbols=batch,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
            )
            bars = self._data_client.get_stock_bars(request)
            df = bars.df.reset_index()
            all_frames.append(df)
        if not all_frames:
            return pd.DataFrame()
        return pd.concat(all_frames, ignore_index=True)

    def get_news(self, tickers: list[str], start: datetime, end: datetime) -> list[NewsArticle]:
        # Alpaca news endpoint — stubbed for now, will implement in sentiment signal
        return []
