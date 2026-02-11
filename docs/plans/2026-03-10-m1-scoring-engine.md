# M1: Scoring Engine + CLI Analysis — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a working `python analyze.py NVDA AMD PLTR` that scores stocks and outputs buy/hold/sell recommendations.

**Architecture:** Signal modules compute individual scores (trend, relative strength, volatility, liquidity). Portfolio-analyst combines them using strategy config weights. Risk-manager reviews portfolio-level concerns. Output to terminal + JSON.

**Tech Stack:** Python 3.12+, alpaca-py, duckdb, pandas, numpy, pyyaml, python-dotenv

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: all directory `__init__.py` files

**Step 1: Create pyproject.toml**

```toml
[project]
name = "quant-autoresearch"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "alpaca-py>=0.35.0",
    "duckdb>=1.2.0",
    "pandas>=2.2.0",
    "numpy>=2.0.0",
    "pyyaml>=6.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]
```

**Step 2: Create .gitignore**

```
.env
*.duckdb
*.duckdb.wal
output/
__pycache__/
*.pyc
.venv/
*.egg-info/
```

**Step 3: Create .env.example**

```
ALPACA_API_KEY=your_key_here
ALPACA_SECRET=your_secret_here
```

**Step 4: Create directories and __init__.py files**

```bash
mkdir -p src/agents/signals src/research src/data src/models src/strategy src/output tests output strategies experiments .claude/agents
touch src/__init__.py src/agents/__init__.py src/agents/signals/__init__.py src/research/__init__.py src/data/__init__.py src/models/__init__.py src/strategy/__init__.py src/output/__init__.py tests/__init__.py
```

**Step 5: Install deps and commit**

```bash
pip install -e ".[dev]"
git add pyproject.toml .gitignore .env.example src/ tests/ strategies/ experiments/ .claude/
git commit -m "scaffold project structure and deps"
```

---

### Task 2: Data Models

**Files:**
- Create: `src/models/types.py`
- Create: `tests/test_types.py`

**Step 1: Write failing tests**

```python
# tests/test_types.py
from datetime import datetime
from src.models.types import Stock, SignalScore, Recommendation, PortfolioReport, NewsArticle

def test_stock_creation():
    s = Stock(ticker="AAPL", name="Apple Inc.", exchange="NASDAQ", sector="Technology")
    assert s.ticker == "AAPL"
    assert s.sector == "Technology"

def test_signal_score_creation():
    score = SignalScore(
        ticker="AAPL", signal="trend", score=85.0,
        confidence=0.9, components={"momentum_3m": 90}, timestamp=datetime.now()
    )
    assert 0 <= score.score <= 100
    assert 0 <= score.confidence <= 1

def test_recommendation_creation():
    r = Recommendation(
        ticker="AAPL", action="buy", confidence=0.85,
        composite_score=78.3,
        signal_scores={"trend": 91.2, "volatility": 65.0},
        rationale="Strong momentum above all SMAs",
        invalidation="Break below 50-day SMA",
        risk_params={"stop_loss": 142.50, "max_position_pct": 8.0},
    )
    assert r.action in ("buy", "hold", "sell")

def test_portfolio_report_creation():
    rec = Recommendation(
        ticker="AAPL", action="buy", confidence=0.8, composite_score=75.0,
        signal_scores={}, rationale="", invalidation="", risk_params={},
    )
    report = PortfolioReport(
        date=datetime.now(), strategy_version="0.1",
        recommendations=[rec], warnings=["Test warning"],
    )
    assert len(report.recommendations) == 1

def test_news_article():
    a = NewsArticle(ticker="AAPL", headline="Apple beats", source="Reuters",
                    published=datetime.now())
    assert a.ticker == "AAPL"
```

**Step 2: Run tests — verify they fail**

Run: `pytest tests/test_types.py -v`
Expected: FAIL — cannot import

**Step 3: Implement types**

```python
# src/models/types.py
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Stock:
    ticker: str
    name: str
    exchange: str
    sector: str = ""
    industry: str = ""
    market_cap: float = 0.0

@dataclass
class SignalScore:
    ticker: str
    signal: str         # which signal produced this
    score: float        # 0-100 normalized
    confidence: float   # 0-1
    components: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class Recommendation:
    ticker: str
    action: str             # "buy" / "hold" / "sell"
    confidence: float       # 0-1
    composite_score: float  # 0-100
    signal_scores: dict = field(default_factory=dict)   # signal_name -> score
    rationale: str = ""
    invalidation: str = ""
    risk_params: dict = field(default_factory=dict)     # stop_loss, max_position_pct

@dataclass
class PortfolioReport:
    date: datetime
    strategy_version: str
    recommendations: list[Recommendation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    strongest: str = ""
    weakest: str = ""

@dataclass
class NewsArticle:
    ticker: str
    headline: str
    source: str
    published: datetime
    url: str = ""
    summary: str = ""
```

**Step 4: Run tests — verify pass**

Run: `pytest tests/test_types.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/models/types.py tests/test_types.py
git commit -m "add core data models"
```

---

### Task 3: Strategy Config Loader

**Files:**
- Create: `src/strategy/config.py`
- Create: `strategies/v0.1.yaml`
- Create: `tests/test_strategy_config.py`

**Step 1: Write failing tests**

```python
# tests/test_strategy_config.py
from pathlib import Path
from src.strategy.config import StrategyConfig, load_strategy

def test_load_strategy_from_yaml(tmp_path):
    yaml_content = """
version: "0.1"
name: "test-baseline"
weights:
  trend: 0.35
  relative_strength: 0.10
  volatility: 0.15
  liquidity: 0.10
  fundamentals: 0.20
  sentiment: 0.10
thresholds:
  buy: 70
  hold_min: 40
  sell: 40
filters:
  min_price: 5.0
  min_avg_volume: 500000
  max_annual_volatility: 100
"""
    config_file = tmp_path / "test.yaml"
    config_file.write_text(yaml_content)
    config = load_strategy(str(config_file))
    assert config.version == "0.1"
    assert config.weights["trend"] == 0.35
    assert sum(config.weights.values()) == pytest.approx(1.0)
    assert config.thresholds["buy"] == 70

def test_weights_must_sum_to_one(tmp_path):
    yaml_content = """
version: "0.1"
name: "bad"
weights:
  trend: 0.5
  relative_strength: 0.9
thresholds:
  buy: 70
  hold_min: 40
  sell: 40
filters: {}
"""
    config_file = tmp_path / "bad.yaml"
    config_file.write_text(yaml_content)
    with pytest.raises(ValueError, match="[Ww]eights"):
        load_strategy(str(config_file))

def test_thresholds_buy_above_sell(tmp_path):
    yaml_content = """
version: "0.1"
name: "bad"
weights:
  trend: 1.0
thresholds:
  buy: 30
  hold_min: 40
  sell: 70
filters: {}
"""
    config_file = tmp_path / "bad.yaml"
    config_file.write_text(yaml_content)
    with pytest.raises(ValueError, match="[Tt]hreshold"):
        load_strategy(str(config_file))

import pytest
```

**Step 2: Run tests — verify they fail**

Run: `pytest tests/test_strategy_config.py -v`
Expected: FAIL — cannot import

**Step 3: Implement strategy config**

```python
# src/strategy/config.py
from dataclasses import dataclass, field
import yaml

@dataclass
class StrategyConfig:
    version: str
    name: str
    weights: dict[str, float]
    thresholds: dict[str, float]
    filters: dict[str, float] = field(default_factory=dict)
    overrides: str | None = None

def load_strategy(path: str) -> StrategyConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)

    config = StrategyConfig(
        version=str(raw["version"]),
        name=raw["name"],
        weights=raw["weights"],
        thresholds=raw["thresholds"],
        filters=raw.get("filters", {}),
        overrides=raw.get("overrides"),
    )
    _validate(config)
    return config

def _validate(config: StrategyConfig):
    # Weights must sum to ~1.0
    total = sum(config.weights.values())
    if abs(total - 1.0) > 0.01:
        raise ValueError(f"Weights must sum to 1.0, got {total}")

    # Buy threshold must be above sell
    if config.thresholds.get("buy", 0) <= config.thresholds.get("sell", 0):
        raise ValueError("Buy threshold must be above sell threshold")
```

**Step 4: Create baseline strategy config**

```yaml
# strategies/v0.1.yaml
version: "0.1"
name: "baseline"
weights:
  trend: 0.35
  relative_strength: 0.10
  volatility: 0.15
  liquidity: 0.10
  fundamentals: 0.20
  sentiment: 0.10
thresholds:
  buy: 70
  hold_min: 40
  sell: 40
filters:
  min_price: 5.0
  min_avg_volume: 500000
  max_annual_volatility: 100
overrides: null
```

**Step 5: Run tests — verify pass**

Run: `pytest tests/test_strategy_config.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/strategy/config.py strategies/v0.1.yaml tests/test_strategy_config.py
git commit -m "add strategy config loader with validation"
```

---

### Task 4: Data Provider ABC + Alpaca Implementation

**Files:**
- Create: `src/data/provider.py`
- Create: `src/data/alpaca.py`
- Create: `tests/test_alpaca.py`

**Step 1: Write DataProvider ABC**

```python
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
```

**Step 2: Write tests for AlpacaProvider**

```python
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
```

**Step 3: Run tests — verify they fail**

Run: `pytest tests/test_alpaca.py -v`
Expected: FAIL — cannot import

**Step 4: Implement AlpacaProvider**

```python
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
```

**Step 5: Run tests — verify pass**

Run: `pytest tests/test_alpaca.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/data/provider.py src/data/alpaca.py tests/test_alpaca.py
git commit -m "add DataProvider ABC and AlpacaProvider"
```

---

### Task 5: DuckDB Storage Layer

**Files:**
- Create: `src/data/db.py`
- Create: `tests/test_db.py`

**Step 1: Write failing tests**

```python
# tests/test_db.py
import pandas as pd
from datetime import datetime
from src.data.db import Storage

def test_store_and_retrieve_bars(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    bars = pd.DataFrame({
        "symbol": ["AAPL", "AAPL"],
        "timestamp": [datetime(2026, 3, 1), datetime(2026, 3, 2)],
        "open": [150.0, 151.0],
        "high": [155.0, 156.0],
        "low": [149.0, 150.0],
        "close": [154.0, 155.0],
        "volume": [1000000, 1100000],
    })
    db.store_bars(bars)
    result = db.get_bars(["AAPL"], datetime(2026, 3, 1), datetime(2026, 3, 3))
    assert len(result) == 2

def test_store_and_retrieve_scores(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    db.store_score(
        run_date=datetime(2026, 3, 10), ticker="AAPL", signal="trend",
        score=85.0, confidence=0.9, components={"momentum_3m": 90}
    )
    scores = db.get_scores(datetime(2026, 3, 10))
    assert len(scores) == 1
    assert scores[0]["ticker"] == "AAPL"

def test_get_bars_multiple_tickers(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    bars = pd.DataFrame({
        "symbol": ["AAPL", "MSFT"],
        "timestamp": [datetime(2026, 3, 1), datetime(2026, 3, 1)],
        "open": [150.0, 300.0],
        "high": [155.0, 305.0],
        "low": [149.0, 298.0],
        "close": [154.0, 303.0],
        "volume": [1000000, 800000],
    })
    db.store_bars(bars)
    result = db.get_bars(["AAPL", "MSFT"], datetime(2026, 3, 1), datetime(2026, 3, 2))
    assert len(result) == 2

def test_bars_deduplication(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    bars = pd.DataFrame({
        "symbol": ["AAPL"],
        "timestamp": [datetime(2026, 3, 1)],
        "open": [150.0], "high": [155.0], "low": [149.0], "close": [154.0], "volume": [1000000],
    })
    db.store_bars(bars)
    db.store_bars(bars)  # insert same data again
    result = db.get_bars(["AAPL"], datetime(2026, 3, 1), datetime(2026, 3, 2))
    assert len(result) == 1
```

**Step 2: Run tests — verify they fail**

Run: `pytest tests/test_db.py -v`
Expected: FAIL

**Step 3: Implement Storage**

```python
# src/data/db.py
import duckdb
import json
import pandas as pd
from datetime import datetime

class Storage:
    def __init__(self, db_path: str = "data/trading_agent.duckdb"):
        self.conn = duckdb.connect(db_path)
        self._init_tables()

    def _init_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bars (
                symbol VARCHAR,
                timestamp TIMESTAMP,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                PRIMARY KEY (symbol, timestamp)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                run_date DATE,
                ticker VARCHAR,
                signal VARCHAR,
                score DOUBLE,
                confidence DOUBLE,
                components JSON,
                PRIMARY KEY (run_date, ticker, signal)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                run_date DATE,
                ticker VARCHAR,
                action VARCHAR,
                confidence DOUBLE,
                composite_score DOUBLE,
                signal_scores JSON,
                rationale VARCHAR,
                invalidation VARCHAR,
                risk_params JSON,
                PRIMARY KEY (run_date, ticker)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id VARCHAR PRIMARY KEY,
                parent_version VARCHAR,
                config_diff JSON,
                metrics JSON,
                decision VARCHAR,
                created_at TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS strategy_versions (
                version VARCHAR PRIMARY KEY,
                config_hash VARCHAR,
                promoted_date TIMESTAMP,
                metrics JSON
            )
        """)

    def store_bars(self, bars_df: pd.DataFrame):
        self.conn.execute(
            "INSERT OR REPLACE INTO bars SELECT * FROM bars_df"
        )

    def get_bars(self, tickers: list[str], start: datetime, end: datetime) -> pd.DataFrame:
        return self.conn.execute(
            "SELECT * FROM bars WHERE symbol IN (SELECT UNNEST(?)) AND timestamp >= ? AND timestamp < ? ORDER BY symbol, timestamp",
            [tickers, start, end]
        ).fetchdf()

    def store_score(self, run_date: datetime, ticker: str, signal: str,
                    score: float, confidence: float, components: dict):
        self.conn.execute(
            "INSERT OR REPLACE INTO scores VALUES (?, ?, ?, ?, ?, ?)",
            [run_date, ticker, signal, score, confidence, json.dumps(components)]
        )

    def get_scores(self, run_date: datetime) -> list[dict]:
        return self.conn.execute(
            "SELECT * FROM scores WHERE run_date = ?", [run_date]
        ).fetchdf().to_dict("records")

    def store_recommendation(self, run_date: datetime, rec: dict):
        self.conn.execute(
            "INSERT OR REPLACE INTO recommendations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [run_date, rec["ticker"], rec["action"], rec["confidence"],
             rec["composite_score"], json.dumps(rec.get("signal_scores", {})),
             rec.get("rationale", ""), rec.get("invalidation", ""),
             json.dumps(rec.get("risk_params", {}))]
        )

    def close(self):
        self.conn.close()
```

**Step 4: Run tests — verify pass**

Run: `pytest tests/test_db.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/data/db.py tests/test_db.py
git commit -m "add DuckDB storage layer"
```

---

### Task 6: Signal Base Class + Trend Signal

**Files:**
- Create: `src/agents/base.py`
- Create: `src/agents/signals/trend.py`
- Create: `tests/test_trend.py`

**Step 1: Write BaseSignal**

```python
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
```

**Step 2: Write failing trend tests**

```python
# tests/test_trend.py
import pandas as pd
import numpy as np
from datetime import datetime
from src.agents.signals.trend import TrendSignal

def _make_uptrend(days=252):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    prices = 100 * np.cumprod(1 + np.random.normal(0.001, 0.008, days))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices,
        "volume": np.random.randint(500_000, 2_000_000, days),
    })

def _make_downtrend(days=252):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    prices = 100 * np.cumprod(1 + np.random.normal(-0.001, 0.008, days))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 1.01, "high": prices * 1.02,
        "low": prices * 0.99, "close": prices,
        "volume": np.random.randint(500_000, 2_000_000, days),
    })

def test_uptrend_scores_higher():
    signal = TrendSignal()
    up = signal.score("UP", _make_uptrend())
    down = signal.score("DOWN", _make_downtrend())
    assert up.score > down.score

def test_score_in_range():
    signal = TrendSignal()
    result = signal.score("TEST", _make_uptrend())
    assert 0 <= result.score <= 100
    assert result.signal == "trend"

def test_components_present():
    signal = TrendSignal()
    result = signal.score("TEST", _make_uptrend())
    assert "momentum" in result.components
    assert "sma_structure" in result.components
    assert "vol_contraction" in result.components
    assert "volume_confirm" in result.components

def test_explain_returns_string():
    signal = TrendSignal()
    result = signal.score("TEST", _make_uptrend())
    explanation = signal.explain(result)
    assert isinstance(explanation, str)
    assert "TEST" in explanation
```

**Step 3: Run tests — verify they fail**

Run: `pytest tests/test_trend.py -v`
Expected: FAIL

**Step 4: Implement TrendSignal**

```python
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
```

**Step 5: Run tests — verify pass**

Run: `pytest tests/test_trend.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/agents/base.py src/agents/signals/trend.py tests/test_trend.py
git commit -m "add BaseSignal ABC and TrendSignal"
```

---

### Task 7: Relative Strength Signal

**Files:**
- Create: `src/agents/signals/relative_strength.py`
- Create: `tests/test_relative_strength.py`

**Step 1: Write failing tests**

```python
# tests/test_relative_strength.py
import pandas as pd
import numpy as np
from datetime import datetime
from src.agents.signals.relative_strength import RelativeStrengthSignal

def _make_bars(daily_return=0.001, days=252):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    prices = 100 * np.cumprod(1 + np.random.normal(daily_return, 0.008, days))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices,
        "volume": np.random.randint(500_000, 2_000_000, days),
    })

def test_outperformer_scores_higher():
    signal = RelativeStrengthSignal()
    spy = _make_bars(daily_return=0.0005)
    strong = signal.score("STRONG", _make_bars(daily_return=0.002), benchmark_bars=spy)
    weak = signal.score("WEAK", _make_bars(daily_return=-0.001), benchmark_bars=spy)
    assert strong.score > weak.score

def test_score_in_range():
    signal = RelativeStrengthSignal()
    spy = _make_bars()
    result = signal.score("TEST", _make_bars(), benchmark_bars=spy)
    assert 0 <= result.score <= 100
    assert result.signal == "relative_strength"

def test_no_benchmark_returns_neutral():
    signal = RelativeStrengthSignal()
    result = signal.score("TEST", _make_bars(), benchmark_bars=None)
    assert result.score == 50.0
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_relative_strength.py -v`

**Step 3: Implement**

```python
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
```

**Step 4: Run tests — verify pass, commit**

```bash
pytest tests/test_relative_strength.py -v
git add src/agents/signals/relative_strength.py tests/test_relative_strength.py
git commit -m "add RelativeStrengthSignal"
```

---

### Task 8: Volatility Signal

**Files:**
- Create: `src/agents/signals/volatility.py`
- Create: `tests/test_volatility.py`

**Step 1: Write failing tests**

```python
# tests/test_volatility.py
import pandas as pd
import numpy as np
from datetime import datetime
from src.agents.signals.volatility import VolatilitySignal

def _make_stable(days=252):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    prices = 100 + np.cumsum(np.random.normal(0.05, 0.3, days))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 0.999, "high": prices * 1.005,
        "low": prices * 0.995, "close": prices, "volume": [2_000_000] * days,
    })

def _make_volatile(days=252):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    prices = 100 + np.cumsum(np.random.normal(0, 3, days))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 0.97, "high": prices * 1.05,
        "low": prices * 0.95, "close": prices, "volume": [2_000_000] * days,
    })

def test_stable_scores_higher():
    signal = VolatilitySignal()
    stable = signal.score("SAFE", _make_stable())
    wild = signal.score("WILD", _make_volatile())
    assert stable.score > wild.score

def test_components_include_risk_params():
    signal = VolatilitySignal()
    result = signal.score("TEST", _make_stable())
    assert "annual_vol_pct" in result.components
    assert "max_drawdown_pct" in result.components
    assert "stop_loss" in result.components
    assert "max_position_pct" in result.components

def test_score_in_range():
    signal = VolatilitySignal()
    result = signal.score("TEST", _make_stable())
    assert 0 <= result.score <= 100
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_volatility.py -v`

**Step 3: Implement**

```python
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
```

**Step 4: Run tests — verify pass, commit**

```bash
pytest tests/test_volatility.py -v
git add src/agents/signals/volatility.py tests/test_volatility.py
git commit -m "add VolatilitySignal with risk params"
```

---

### Task 9: Liquidity Signal

**Files:**
- Create: `src/agents/signals/liquidity.py`
- Create: `tests/test_liquidity.py`

**Step 1: Write failing tests**

```python
# tests/test_liquidity.py
import pandas as pd
import numpy as np
from datetime import datetime
from src.agents.signals.liquidity import LiquiditySignal

def _make_bars(avg_volume=1_000_000, price=100.0, days=60):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    return pd.DataFrame({
        "timestamp": dates, "open": [price]*days, "high": [price*1.01]*days,
        "low": [price*0.99]*days, "close": [price]*days,
        "volume": np.random.randint(int(avg_volume*0.8), int(avg_volume*1.2), days),
    })

def test_high_volume_scores_higher():
    signal = LiquiditySignal()
    liquid = signal.score("LIQ", _make_bars(avg_volume=5_000_000, price=100))
    illiquid = signal.score("ILLIQ", _make_bars(avg_volume=50_000, price=5))
    assert liquid.score > illiquid.score

def test_score_in_range():
    signal = LiquiditySignal()
    result = signal.score("TEST", _make_bars())
    assert 0 <= result.score <= 100
    assert result.signal == "liquidity"
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_liquidity.py -v`

**Step 3: Implement**

```python
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
```

**Step 4: Run tests — verify pass, commit**

```bash
pytest tests/test_liquidity.py -v
git add src/agents/signals/liquidity.py tests/test_liquidity.py
git commit -m "add LiquiditySignal"
```

---

### Task 10: Stubbed Fundamentals + Sentiment Signals

**Files:**
- Create: `src/agents/signals/fundamentals.py`
- Create: `src/agents/signals/sentiment.py`
- Create: `tests/test_stubs.py`

**Step 1: Write tests**

```python
# tests/test_stubs.py
import pandas as pd
import numpy as np
from datetime import datetime
from src.agents.signals.fundamentals import FundamentalsSignal
from src.agents.signals.sentiment import SentimentSignal

def _make_bars(days=60):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    return pd.DataFrame({
        "timestamp": dates, "open": [100]*days, "high": [101]*days,
        "low": [99]*days, "close": [100]*days, "volume": [1_000_000]*days,
    })

def test_fundamentals_stub_returns_neutral():
    signal = FundamentalsSignal()
    result = signal.score("AAPL", _make_bars())
    assert result.score == 50.0
    assert result.confidence == 0.0

def test_sentiment_stub_returns_neutral():
    signal = SentimentSignal()
    result = signal.score("AAPL", _make_bars())
    assert result.score == 50.0
    assert result.confidence == 0.0

def test_fundamentals_explain():
    signal = FundamentalsSignal()
    result = signal.score("AAPL", _make_bars())
    assert "stubbed" in signal.explain(result).lower() or "not available" in signal.explain(result).lower()

def test_sentiment_explain():
    signal = SentimentSignal()
    result = signal.score("AAPL", _make_bars())
    assert "stubbed" in signal.explain(result).lower() or "not available" in signal.explain(result).lower()
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_stubs.py -v`

**Step 3: Implement both stubs**

```python
# src/agents/signals/fundamentals.py
import pandas as pd
from datetime import datetime
from src.agents.base import BaseSignal
from src.models.types import SignalScore

class FundamentalsSignal(BaseSignal):
    name = "fundamentals"

    def score(self, ticker: str, bars: pd.DataFrame, benchmark_bars: pd.DataFrame | None = None) -> SignalScore:
        return SignalScore(
            ticker=ticker, signal=self.name, score=50.0, confidence=0.0,
            components={"status": "stubbed"}, timestamp=datetime.now(),
        )

    def explain(self, score: SignalScore) -> str:
        return f"{score.ticker} fundamentals: stubbed — data not yet available"
```

```python
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
```

**Step 4: Run tests — verify pass, commit**

```bash
pytest tests/test_stubs.py -v
git add src/agents/signals/fundamentals.py src/agents/signals/sentiment.py tests/test_stubs.py
git commit -m "add stubbed fundamentals and sentiment signals"
```

---

### Task 11: Portfolio Analyst

**Files:**
- Create: `src/agents/portfolio_analyst.py`
- Create: `tests/test_portfolio_analyst.py`

**Step 1: Write failing tests**

```python
# tests/test_portfolio_analyst.py
import pandas as pd
import numpy as np
from datetime import datetime
from src.agents.portfolio_analyst import PortfolioAnalyst
from src.strategy.config import StrategyConfig

def _make_config():
    return StrategyConfig(
        version="0.1", name="test",
        weights={"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                 "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
        thresholds={"buy": 70, "hold_min": 40, "sell": 40},
        filters={},
    )

def _make_strong_bars(days=252):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    prices = 100 * np.cumprod(1 + np.random.normal(0.002, 0.008, days))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices,
        "volume": np.random.randint(1_000_000, 3_000_000, days),
    })

def _make_weak_bars(days=252):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    prices = 100 * np.cumprod(1 + np.random.normal(-0.002, 0.015, days))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 1.01, "high": prices * 1.02,
        "low": prices * 0.98, "close": prices,
        "volume": np.random.randint(100_000, 300_000, days),
    })

def test_analyze_returns_recommendations():
    analyst = PortfolioAnalyst(_make_config())
    spy = _make_strong_bars()
    bars = {"STRONG": _make_strong_bars(), "WEAK": _make_weak_bars(), "SPY": spy}
    recs = analyst.analyze(["STRONG", "WEAK"], bars)
    assert len(recs) == 2
    assert all(r.action in ("buy", "hold", "sell") for r in recs)

def test_strong_stock_scores_higher():
    analyst = PortfolioAnalyst(_make_config())
    spy = _make_strong_bars()
    bars = {"STRONG": _make_strong_bars(), "WEAK": _make_weak_bars(), "SPY": spy}
    recs = analyst.analyze(["STRONG", "WEAK"], bars)
    rec_map = {r.ticker: r for r in recs}
    assert rec_map["STRONG"].composite_score > rec_map["WEAK"].composite_score

def test_recommendation_has_required_fields():
    analyst = PortfolioAnalyst(_make_config())
    bars = {"AAPL": _make_strong_bars(), "SPY": _make_strong_bars()}
    recs = analyst.analyze(["AAPL"], bars)
    rec = recs[0]
    assert rec.rationale != ""
    assert rec.invalidation != ""
    assert "stop_loss" in rec.risk_params
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_portfolio_analyst.py -v`

**Step 3: Implement**

```python
# src/agents/portfolio_analyst.py
from src.strategy.config import StrategyConfig
from src.models.types import Recommendation, SignalScore
from src.agents.signals.trend import TrendSignal
from src.agents.signals.relative_strength import RelativeStrengthSignal
from src.agents.signals.volatility import VolatilitySignal
from src.agents.signals.liquidity import LiquiditySignal
from src.agents.signals.fundamentals import FundamentalsSignal
from src.agents.signals.sentiment import SentimentSignal
import pandas as pd

class PortfolioAnalyst:
    def __init__(self, config: StrategyConfig):
        self.config = config
        self.signals = {
            "trend": TrendSignal(),
            "relative_strength": RelativeStrengthSignal(),
            "volatility": VolatilitySignal(),
            "liquidity": LiquiditySignal(),
            "fundamentals": FundamentalsSignal(),
            "sentiment": SentimentSignal(),
        }

    def analyze(self, tickers: list[str], bars: dict[str, pd.DataFrame]) -> list[Recommendation]:
        spy_bars = bars.get("SPY")
        recommendations = []

        for ticker in tickers:
            ticker_bars = bars.get(ticker)
            if ticker_bars is None or len(ticker_bars) < 20:
                continue

            # Score each signal
            scores: dict[str, SignalScore] = {}
            for name, signal in self.signals.items():
                scores[name] = signal.score(ticker, ticker_bars, benchmark_bars=spy_bars)

            # Weighted composite
            composite = 0.0
            for name, weight in self.config.weights.items():
                if name in scores:
                    composite += scores[name].score * weight

            # Action based on thresholds
            if composite >= self.config.thresholds["buy"]:
                action = "buy"
            elif composite <= self.config.thresholds["sell"]:
                action = "sell"
            else:
                action = "hold"

            # Confidence: weighted average of signal confidences
            total_conf = sum(
                scores[n].confidence * self.config.weights.get(n, 0)
                for n in scores if n in self.config.weights
            )

            # Build rationale from signal explanations
            rationale_parts = []
            for name, signal in self.signals.items():
                if name in scores and scores[name].confidence > 0:
                    rationale_parts.append(signal.explain(scores[name]))
            rationale = "; ".join(rationale_parts)

            # Invalidation from volatility signal
            vol_score = scores.get("volatility")
            invalidation = ""
            risk_params = {}
            if vol_score and not vol_score.components.get("insufficient_data"):
                risk_params = {
                    "stop_loss": vol_score.components.get("stop_loss", 0),
                    "max_position_pct": vol_score.components.get("max_position_pct", 5),
                }
                invalidation = self.signals["volatility"].explain(vol_score)

            recommendations.append(Recommendation(
                ticker=ticker, action=action, confidence=round(total_conf, 2),
                composite_score=round(composite, 1),
                signal_scores={n: round(s.score, 1) for n, s in scores.items()},
                rationale=rationale, invalidation=invalidation,
                risk_params=risk_params,
            ))

        # Sort by composite score descending
        recommendations.sort(key=lambda r: r.composite_score, reverse=True)
        return recommendations
```

**Step 4: Run tests — verify pass**

Run: `pytest tests/test_portfolio_analyst.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/agents/portfolio_analyst.py tests/test_portfolio_analyst.py
git commit -m "add PortfolioAnalyst combining all signals"
```

---

### Task 12: Risk Manager

**Files:**
- Create: `src/agents/risk_manager.py`
- Create: `tests/test_risk_manager.py`

**Step 1: Write failing tests**

```python
# tests/test_risk_manager.py
import pandas as pd
import numpy as np
from datetime import datetime
from src.agents.risk_manager import RiskManager
from src.models.types import Recommendation

def _rec(ticker, action="buy", score=75.0, sector="Tech"):
    return Recommendation(
        ticker=ticker, action=action, confidence=0.8,
        composite_score=score, signal_scores={"sector": sector},
        rationale="", invalidation="", risk_params={"max_position_pct": 10},
    )

def test_warns_sector_concentration():
    rm = RiskManager()
    recs = [_rec("A", sector="Tech"), _rec("B", sector="Tech"),
            _rec("C", sector="Tech"), _rec("D", sector="Tech")]
    warnings = rm.review(recs)
    assert any("concentration" in w.lower() or "sector" in w.lower() for w in warnings)

def test_no_warning_for_diversified():
    rm = RiskManager()
    recs = [_rec("A", sector="Tech"), _rec("B", sector="Health"),
            _rec("C", sector="Energy")]
    warnings = rm.review(recs)
    sector_warnings = [w for w in warnings if "sector" in w.lower()]
    assert len(sector_warnings) == 0

def test_warns_score_instability():
    rm = RiskManager()
    # Score right at threshold boundary
    recs = [_rec("EDGE", action="buy", score=70.5)]
    warnings = rm.review(recs, thresholds={"buy": 70, "sell": 40})
    assert any("unstable" in w.lower() or "borderline" in w.lower() for w in warnings)
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_risk_manager.py -v`

**Step 3: Implement**

```python
# src/agents/risk_manager.py
from collections import Counter
from src.models.types import Recommendation

class RiskManager:
    def __init__(self, max_sector_pct: float = 0.40, stability_margin: float = 3.0):
        self.max_sector_pct = max_sector_pct
        self.stability_margin = stability_margin

    def review(self, recommendations: list[Recommendation],
               thresholds: dict | None = None) -> list[str]:
        warnings = []
        if not recommendations:
            return warnings

        # Sector concentration
        sectors = [r.signal_scores.get("sector", "Unknown") for r in recommendations
                   if r.action == "buy"]
        if sectors:
            counts = Counter(sectors)
            for sector, count in counts.items():
                pct = count / len(recommendations)
                if pct > self.max_sector_pct:
                    warnings.append(
                        f"Sector concentration: {count}/{len(recommendations)} "
                        f"recommendations in {sector} ({pct:.0%})"
                    )

        # Score stability: flag recommendations near threshold boundaries
        if thresholds:
            buy_thresh = thresholds.get("buy", 70)
            sell_thresh = thresholds.get("sell", 40)
            for r in recommendations:
                if r.action == "buy" and r.composite_score < buy_thresh + self.stability_margin:
                    warnings.append(
                        f"Borderline/unstable: {r.ticker} buy at {r.composite_score:.1f} "
                        f"(threshold {buy_thresh}, margin {self.stability_margin})"
                    )
                elif r.action == "sell" and r.composite_score > sell_thresh - self.stability_margin:
                    warnings.append(
                        f"Borderline/unstable: {r.ticker} sell at {r.composite_score:.1f} "
                        f"(threshold {sell_thresh}, margin {self.stability_margin})"
                    )

        # Total position size check
        buy_recs = [r for r in recommendations if r.action == "buy"]
        total_alloc = sum(r.risk_params.get("max_position_pct", 10) for r in buy_recs)
        if total_alloc > 100:
            warnings.append(
                f"Total allocation {total_alloc:.0f}% exceeds 100% — reduce position sizes"
            )

        return warnings
```

**Step 4: Run tests — verify pass, commit**

```bash
pytest tests/test_risk_manager.py -v
git add src/agents/risk_manager.py tests/test_risk_manager.py
git commit -m "add RiskManager with concentration and stability checks"
```

---

### Task 13: Output Formatters

**Files:**
- Create: `src/output/console.py`
- Create: `src/output/json_writer.py`
- Create: `tests/test_output.py`

**Step 1: Write tests**

```python
# tests/test_output.py
import json
from datetime import datetime
from src.output.console import format_report
from src.output.json_writer import write_report
from src.models.types import Recommendation, PortfolioReport

def _sample_report():
    recs = [
        Recommendation("NVDA", "buy", 0.85, 82.3,
                        {"trend": 91.2, "volatility": 65.0, "sector": "Technology"},
                        "Strong momentum", "Break below 50 SMA",
                        {"stop_loss": 142.5, "max_position_pct": 8.0}),
        Recommendation("PLTR", "hold", 0.60, 55.1,
                        {"trend": 60.0, "volatility": 45.0, "sector": "Technology"},
                        "Mixed signals", "Loss of uptrend",
                        {"stop_loss": 22.0, "max_position_pct": 5.0}),
        Recommendation("INTC", "sell", 0.75, 32.0,
                        {"trend": 25.0, "volatility": 30.0, "sector": "Technology"},
                        "Weak trend, below SMAs", "N/A",
                        {"stop_loss": 0, "max_position_pct": 0}),
    ]
    return PortfolioReport(
        date=datetime.now(), strategy_version="0.1",
        recommendations=recs, warnings=["Sector concentration: 3/3 in Technology"],
        strongest="NVDA", weakest="INTC",
    )

def test_format_report_contains_tickers():
    output = format_report(_sample_report())
    assert "NVDA" in output
    assert "PLTR" in output
    assert "buy" in output.lower()
    assert "sell" in output.lower()

def test_format_report_contains_warnings():
    output = format_report(_sample_report())
    assert "concentration" in output.lower()

def test_write_report_json(tmp_path):
    report = _sample_report()
    filepath = write_report(report, str(tmp_path))
    data = json.loads(open(filepath).read())
    assert data["strategy_version"] == "0.1"
    assert len(data["recommendations"]) == 3
    assert data["recommendations"][0]["ticker"] == "NVDA"
```

**Step 2: Run tests — verify fail**

Run: `pytest tests/test_output.py -v`

**Step 3: Implement console formatter**

```python
# src/output/console.py
from src.models.types import PortfolioReport

SIGNAL_COLS = ["trend", "relative_strength", "volatility", "liquidity", "fundamentals", "sentiment"]

def format_report(report: PortfolioReport) -> str:
    lines = [
        f"\n{'='*70}",
        f"  Portfolio Analysis — {report.date.strftime('%Y-%m-%d')}  (strategy {report.strategy_version})",
        f"{'='*70}\n",
    ]

    # Summary
    if report.strongest:
        lines.append(f"  Strongest: {report.strongest}")
    if report.weakest:
        lines.append(f"  Weakest:   {report.weakest}")
    lines.append("")

    # Table header
    header = f" {'Ticker':<6} {'Action':<6} {'Score':>6} {'Conf':>5}"
    for col in SIGNAL_COLS:
        short = col[:5].title()
        header += f" {short:>6}"
    lines.append(header)
    lines.append("-" * len(header))

    # Rows
    for r in report.recommendations:
        action_str = r.action.upper()
        row = f" {r.ticker:<6} {action_str:<6} {r.composite_score:>6.1f} {r.confidence:>5.0%}"
        for col in SIGNAL_COLS:
            val = r.signal_scores.get(col, 0)
            row += f" {val:>6.1f}"
        lines.append(row)

    # Warnings
    if report.warnings:
        lines.append("")
        for w in report.warnings:
            lines.append(f"  ! {w}")

    # Per-stock details
    lines.append("")
    for r in report.recommendations:
        lines.append(f"-- {r.ticker} [{r.action.upper()}] --")
        if r.rationale:
            lines.append(f"  Rationale: {r.rationale}")
        if r.risk_params.get("stop_loss"):
            lines.append(f"  Risk: Stop ${r.risk_params['stop_loss']}, max {r.risk_params.get('max_position_pct', '?')}% portfolio")
        if r.invalidation:
            lines.append(f"  Invalidation: {r.invalidation}")
        lines.append("")

    return "\n".join(lines)
```

**Step 4: Implement JSON writer**

```python
# src/output/json_writer.py
import json
from datetime import date
from dataclasses import asdict
from pathlib import Path
from src.models.types import PortfolioReport

def write_report(report: PortfolioReport, output_dir: str = "output") -> str:
    path = Path(output_dir)
    path.mkdir(exist_ok=True)
    today = date.today().isoformat()
    data = {
        "date": today,
        "strategy_version": report.strategy_version,
        "strongest": report.strongest,
        "weakest": report.weakest,
        "recommendations": [asdict(r) for r in report.recommendations],
        "warnings": report.warnings,
    }
    filepath = path / f"analysis-{today}.json"
    filepath.write_text(json.dumps(data, indent=2, default=str))
    return str(filepath)
```

**Step 5: Run tests — verify pass, commit**

```bash
pytest tests/test_output.py -v
git add src/output/ tests/test_output.py
git commit -m "add console and JSON output formatters"
```

---

### Task 14: CLI Entrypoint (analyze.py)

**Files:**
- Create: `analyze.py`

**Step 1: Implement the CLI pipeline**

```python
#!/usr/bin/env python3
"""Quant Autoresearch Agent — Portfolio Analysis CLI."""
import argparse
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.data.alpaca import AlpacaProvider
from src.data.db import Storage
from src.agents.portfolio_analyst import PortfolioAnalyst
from src.agents.risk_manager import RiskManager
from src.strategy.config import load_strategy
from src.models.types import PortfolioReport
from src.output.console import format_report
from src.output.json_writer import write_report

DEFAULT_STRATEGY = "strategies/v0.1.yaml"

def main():
    parser = argparse.ArgumentParser(description="Analyze stocks for buy/hold/sell")
    parser.add_argument("tickers", nargs="+", help="Stock tickers to analyze")
    parser.add_argument("--strategy", default=DEFAULT_STRATEGY, help="Strategy config path")
    parser.add_argument("--days", type=int, default=365, help="Days of history to fetch")
    args = parser.parse_args()

    load_dotenv()
    if not os.environ.get("ALPACA_API_KEY"):
        print("Error: Set ALPACA_API_KEY and ALPACA_SECRET in .env")
        sys.exit(1)

    # Load strategy
    print(f"Loading strategy: {args.strategy}")
    config = load_strategy(args.strategy)

    # Init data layer
    provider = AlpacaProvider()
    db = Storage()

    # Fetch bars
    tickers = [t.upper() for t in args.tickers]
    all_tickers = tickers + ["SPY"]  # benchmark
    end = datetime.now()
    start = end - timedelta(days=args.days)

    print(f"Fetching data for {len(tickers)} tickers + SPY...")
    all_bars_df = provider.get_bars(all_tickers, start, end)

    if all_bars_df.empty:
        print("No data returned. Check tickers and API keys.")
        sys.exit(1)

    # Organize bars by ticker
    bars = {}
    for ticker in all_tickers:
        mask = all_bars_df["symbol"] == ticker
        if mask.any():
            bars[ticker] = all_bars_df[mask].sort_values("timestamp").reset_index(drop=True)

    # Cache bars
    db.store_bars(all_bars_df)

    # Analyze
    print("Scoring...")
    analyst = PortfolioAnalyst(config)
    recommendations = analyst.analyze(tickers, bars)

    if not recommendations:
        print("No recommendations generated. Check ticker data.")
        db.close()
        return

    # Risk review
    risk_mgr = RiskManager()
    warnings = risk_mgr.review(recommendations, thresholds=config.thresholds)

    # Build report
    sorted_recs = sorted(recommendations, key=lambda r: r.composite_score, reverse=True)
    report = PortfolioReport(
        date=datetime.now(),
        strategy_version=config.version,
        recommendations=sorted_recs,
        warnings=warnings,
        strongest=sorted_recs[0].ticker if sorted_recs else "",
        weakest=sorted_recs[-1].ticker if sorted_recs else "",
    )

    # Output
    print(format_report(report))
    filepath = write_report(report)
    print(f"\nSaved to {filepath}")

    # Persist scores
    run_date = datetime.now()
    for rec in recommendations:
        db.store_recommendation(run_date, {
            "ticker": rec.ticker, "action": rec.action,
            "confidence": rec.confidence, "composite_score": rec.composite_score,
            "signal_scores": rec.signal_scores, "rationale": rec.rationale,
            "invalidation": rec.invalidation, "risk_params": rec.risk_params,
        })

    db.close()
    print("Done.")

if __name__ == "__main__":
    main()
```

**Step 2: Commit**

```bash
git add analyze.py
git commit -m "add analyze.py CLI entrypoint"
```

---

### Task 15: Integration Test

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write end-to-end test with mocked provider**

```python
# tests/test_integration.py
"""End-to-end test: mock data → scoring → recommendations → output."""
import pandas as pd
import numpy as np
from datetime import datetime
from src.agents.portfolio_analyst import PortfolioAnalyst
from src.agents.risk_manager import RiskManager
from src.strategy.config import StrategyConfig
from src.models.types import PortfolioReport
from src.output.console import format_report
from src.output.json_writer import write_report

def _config():
    return StrategyConfig(
        version="0.1", name="test",
        weights={"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                 "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
        thresholds={"buy": 70, "hold_min": 40, "sell": 40},
        filters={},
    )

def _synthetic_bars(ticker, daily_return=0.001, vol_mult=1.0, days=252):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    prices = 100 * np.cumprod(1 + np.random.normal(daily_return, 0.01 * vol_mult, days))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices,
        "volume": np.random.randint(500_000, 3_000_000, days),
    })

def test_full_pipeline():
    config = _config()
    bars = {
        "STRONG": _synthetic_bars("STRONG", daily_return=0.002),
        "MID":    _synthetic_bars("MID", daily_return=0.0005),
        "WEAK":   _synthetic_bars("WEAK", daily_return=-0.001, vol_mult=2.0),
        "SPY":    _synthetic_bars("SPY", daily_return=0.0005),
    }

    analyst = PortfolioAnalyst(config)
    recs = analyst.analyze(["STRONG", "MID", "WEAK"], bars)

    assert len(recs) == 3
    assert all(r.action in ("buy", "hold", "sell") for r in recs)
    assert all(0 <= r.composite_score <= 100 for r in recs)
    assert all(r.rationale != "" for r in recs)

    # STRONG should generally score highest
    rec_map = {r.ticker: r for r in recs}
    assert rec_map["STRONG"].composite_score > rec_map["WEAK"].composite_score

    # Risk review
    risk_mgr = RiskManager()
    warnings = risk_mgr.review(recs, thresholds=config.thresholds)
    assert isinstance(warnings, list)

    # Output
    report = PortfolioReport(
        date=datetime.now(), strategy_version=config.version,
        recommendations=recs, warnings=warnings,
        strongest=recs[0].ticker, weakest=recs[-1].ticker,
    )
    output = format_report(report)
    assert "STRONG" in output

def test_json_output(tmp_path):
    config = _config()
    bars = {
        "AAPL": _synthetic_bars("AAPL"),
        "SPY": _synthetic_bars("SPY"),
    }
    analyst = PortfolioAnalyst(config)
    recs = analyst.analyze(["AAPL"], bars)
    report = PortfolioReport(
        date=datetime.now(), strategy_version="0.1",
        recommendations=recs, warnings=[],
    )
    filepath = write_report(report, str(tmp_path))
    assert "analysis-" in filepath
```

**Step 2: Run full test suite**

```bash
pytest tests/ -v
```

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "add integration test for full analysis pipeline"
```

---

### Task 16: Claude Code Subagent Prompts (M1 subset)

**Files:**
- Create: `.claude/agents/portfolio-analyst.md`
- Create: `.claude/agents/risk-manager.md`

**Step 1: Write portfolio-analyst subagent**

```markdown
# .claude/agents/portfolio-analyst.md

You are the portfolio analyst for the Quant Autoresearch Agent.

## Role
Score user-provided stocks and generate buy/hold/sell recommendations.

## How to run
Execute the analysis pipeline:
```bash
python analyze.py TICKER1 TICKER2 TICKER3
```

## How to interpret results
- Composite score > 70: BUY signal — strong trend, good risk profile
- Composite score 40-70: HOLD — mixed signals, not compelling either way
- Composite score < 40: SELL — weak trend, poor risk/reward

## What to present to the user
1. The ranked table with scores
2. For each stock: the action, key reasons, and risk parameters
3. Any warnings from the risk manager
4. Your interpretation of the overall portfolio health

## Rules
- Never invent data — all numbers come from the Python pipeline
- If data is missing or stale, say so
- Explain the "why" behind each recommendation
- Flag any borderline calls explicitly
```

**Step 2: Write risk-manager subagent**

```markdown
# .claude/agents/risk-manager.md

You are the risk manager for the Quant Autoresearch Agent.

## Role
Review portfolio-analyst output for portfolio-level risks.

## What to check
1. Sector concentration — are too many picks in one sector?
2. Correlation — are picks likely to move together?
3. Borderline scores — would a small change flip the recommendation?
4. Total allocation — do position sizes exceed 100%?
5. Liquidity — can all positions be entered/exited easily?

## How to run
Risk review runs automatically as part of `python analyze.py`.
To manually investigate, check the JSON output in `output/`.

## Rules
- Be conservative — flag anything questionable
- Never override the quantitative scores
- Your job is to add portfolio awareness, not change individual stock ratings
```

**Step 3: Commit**

```bash
git add .claude/agents/
git commit -m "add portfolio-analyst and risk-manager subagent prompts"
```
