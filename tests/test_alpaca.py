# tests/test_alpaca.py
from unittest.mock import MagicMock, patch
from datetime import datetime
from src.data.alpaca import AlpacaProvider

def test_get_assets_returns_stocks():
    provider = AlpacaProvider.__new__(AlpacaProvider)
    mock_asset = MagicMock()
    mock_asset.symbol = "AAPL"
    mock_asset.name = "Apple Inc."
    mock_asset.exchange = "NASDAQ"
    mock_asset.status = "active"
    mock_asset.tradable = True
    mock_asset.asset_class = "us_equity"
    provider._trading_client = MagicMock()
    provider._trading_client.get_all_assets.return_value = [mock_asset]
    assets = provider.get_assets()
    assert len(assets) == 1
    assert assets[0].ticker == "AAPL"
    assert assets[0].exchange == "NASDAQ"

def test_get_assets_filters_untradable():
    provider = AlpacaProvider.__new__(AlpacaProvider)
    tradable = MagicMock(symbol="AAPL", name="Apple", exchange="NASDAQ", tradable=True)
    untradable = MagicMock(symbol="DEAD", name="Dead Co", exchange="NYSE", tradable=False)
    provider._trading_client = MagicMock()
    provider._trading_client.get_all_assets.return_value = [tradable, untradable]
    assets = provider.get_assets()
    assert len(assets) == 1
    assert assets[0].ticker == "AAPL"
