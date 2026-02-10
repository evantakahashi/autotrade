# Trading Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a weekly stock ranking engine with deterministic Python pipeline + Claude Code subagent wrappers.

**Architecture:** BaseAgent ABC with score()/explain() interface. Alpaca for market data, DuckDB for storage. Pipeline: universe filter → parallel agent scoring → ranking → output.

**Tech Stack:** Python 3.12+, alpaca-py, duckdb, pandas, numpy

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: all `__init__.py` files
- Create: `src/agents/__init__.py`, `src/data/__init__.py`, `src/models/__init__.py`, `src/output/__init__.py`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "trading-agent"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "alpaca-py>=0.35.0",
    "duckdb>=1.2.0",
    "pandas>=2.2.0",
    "numpy>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
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
data/*.duckdb
```

**Step 3: Create .env.example**

```
ALPACA_API_KEY=your_key_here
ALPACA_SECRET=your_secret_here
```

**Step 4: Create all __init__.py and directory structure**

```bash
mkdir -p src/agents src/data src/models src/output output tests .claude/agents
touch src/__init__.py src/agents/__init__.py src/data/__init__.py src/models/__init__.py src/output/__init__.py tests/__init__.py
```

**Step 5: Install deps and commit**

```bash
pip install -e ".[dev]"
git add -A && git commit -m "scaffold project structure and deps"
```

---

### Task 2: Models / Types

**Files:**
- Create: `src/models/types.py`
- Create: `tests/test_types.py`

**Step 1: Write tests for dataclasses**

```python
# tests/test_types.py
from datetime import datetime
from src.models.types import Stock, AgentScore, Ranking, NewsArticle

def test_stock_creation():
    s = Stock(ticker="AAPL", name="Apple Inc.", exchange="NASDAQ", sector="Technology")
    assert s.ticker == "AAPL"
    assert s.sector == "Technology"

def test_agent_score_creation():
    score = AgentScore(
        ticker="AAPL", agent="trend", score=85.0,
        confidence=0.9, components={"momentum_3m": 90}, timestamp=datetime.now()
    )
    assert 0 <= score.score <= 100
    assert 0 <= score.confidence <= 1

def test_ranking_creation():
    r = Ranking(
        ticker="AAPL", rank=1, composite=82.3,
        scores={"trend": 91.2, "sentiment": 78.4},
        explanation="Strong momentum", invalidation="Break below 50 SMA",
        risk_params={"stop_loss": 142.50, "max_position_pct": 8.0}
    )
    assert r.rank == 1
```

**Step 2: Run tests — verify they fail**

```bash
pytest tests/test_types.py -v
```

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
class AgentScore:
    ticker: str
    agent: str
    score: float          # 0-100 normalized
    confidence: float     # 0-1
    components: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class Ranking:
    ticker: str
    rank: int
    composite: float
    scores: dict = field(default_factory=dict)       # agent_name -> score
    explanation: str = ""
    invalidation: str = ""
    risk_params: dict = field(default_factory=dict)   # stop_loss, max_position_pct

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

```bash
pytest tests/test_types.py -v
```

**Step 5: Commit**

```bash
git add src/models/types.py tests/test_types.py && git commit -m "add core dataclasses"
```

---

### Task 3: Data Provider ABC + Alpaca Implementation

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
        """OHLCV bars. Returns DataFrame with columns: ticker, timestamp, open, high, low, close, volume."""

    @abstractmethod
    def get_news(self, tickers: list[str], start: datetime, end: datetime) -> list[NewsArticle]:
        """News articles for given tickers."""
```

**Step 2: Write AlpacaProvider with tests**

Tests should use mocking since we don't want to hit the real API in CI. Write a test that mocks the Alpaca client and verifies our provider transforms the response correctly.

```python
# tests/test_alpaca.py
from unittest.mock import MagicMock, patch
from datetime import datetime
from src.data.alpaca import AlpacaProvider

def test_get_assets_filters_active_equities():
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
```

**Step 3: Implement AlpacaProvider**

```python
# src/data/alpaca.py
import os
import pandas as pd
from datetime import datetime
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
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
        # Alpaca limits to 200 symbols per request — batch
        all_frames = []
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
        # Alpaca news API — use REST client
        # For now return empty; news endpoint needs separate client setup
        return []
```

Note: `get_news` will be fleshed out in the SentimentAgent task. Alpaca's news API uses a different client class.

**Step 4: Run tests — verify pass**

```bash
pytest tests/test_alpaca.py -v
```

**Step 5: Commit**

```bash
git add src/data/ tests/test_alpaca.py && git commit -m "add DataProvider ABC and AlpacaProvider"
```

---

### Task 4: DuckDB Storage Layer

**Files:**
- Create: `src/data/db.py`
- Create: `tests/test_db.py`

**Step 1: Write tests**

```python
# tests/test_db.py
import duckdb
import pandas as pd
from datetime import datetime
from src.data.db import Storage

def test_store_and_retrieve_bars(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    bars = pd.DataFrame({
        "ticker": ["AAPL", "AAPL"],
        "timestamp": [datetime(2026, 3, 1), datetime(2026, 3, 2)],
        "open": [150.0, 151.0],
        "high": [155.0, 156.0],
        "low": [149.0, 150.0],
        "close": [154.0, 155.0],
        "volume": [1000000, 1100000],
    })
    db.store_bars(bars)
    result = db.get_bars("AAPL", datetime(2026, 3, 1), datetime(2026, 3, 3))
    assert len(result) == 2

def test_store_and_retrieve_scores(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    db.store_score(
        run_date=datetime(2026, 3, 10),
        ticker="AAPL", agent="trend",
        score=85.0, confidence=0.9,
        components={"momentum_3m": 90}
    )
    scores = db.get_scores(datetime(2026, 3, 10))
    assert len(scores) == 1
    assert scores[0]["ticker"] == "AAPL"
```

**Step 2: Run tests — verify fail**

```bash
pytest tests/test_db.py -v
```

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
                ticker VARCHAR,
                timestamp TIMESTAMP,
                open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
                volume BIGINT,
                PRIMARY KEY (ticker, timestamp)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                run_date DATE,
                ticker VARCHAR,
                agent VARCHAR,
                score DOUBLE,
                confidence DOUBLE,
                components JSON,
                PRIMARY KEY (run_date, ticker, agent)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS rankings (
                run_date DATE,
                ticker VARCHAR,
                rank INTEGER,
                composite DOUBLE,
                scores_json JSON,
                explanation VARCHAR,
                invalidation VARCHAR,
                risk_params JSON,
                PRIMARY KEY (run_date, ticker)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS news (
                ticker VARCHAR,
                headline VARCHAR,
                source VARCHAR,
                published TIMESTAMP,
                url VARCHAR,
                summary VARCHAR
            )
        """)

    def store_bars(self, bars_df: pd.DataFrame):
        self.conn.execute(
            "INSERT OR REPLACE INTO bars SELECT * FROM bars_df"
        )

    def get_bars(self, ticker: str, start: datetime, end: datetime) -> pd.DataFrame:
        return self.conn.execute(
            "SELECT * FROM bars WHERE ticker = ? AND timestamp >= ? AND timestamp < ? ORDER BY timestamp",
            [ticker, start, end]
        ).fetchdf()

    def store_score(self, run_date: datetime, ticker: str, agent: str,
                    score: float, confidence: float, components: dict):
        self.conn.execute(
            "INSERT OR REPLACE INTO scores VALUES (?, ?, ?, ?, ?, ?)",
            [run_date, ticker, agent, score, confidence, json.dumps(components)]
        )

    def get_scores(self, run_date: datetime) -> list[dict]:
        return self.conn.execute(
            "SELECT * FROM scores WHERE run_date = ?", [run_date]
        ).fetchdf().to_dict("records")

    def store_rankings(self, run_date: datetime, rankings: list[dict]):
        for r in rankings:
            self.conn.execute(
                "INSERT OR REPLACE INTO rankings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [run_date, r["ticker"], r["rank"], r["composite"],
                 json.dumps(r["scores"]), r["explanation"],
                 r["invalidation"], json.dumps(r["risk_params"])]
            )

    def close(self):
        self.conn.close()
```

**Step 4: Run tests — verify pass**

```bash
pytest tests/test_db.py -v
```

**Step 5: Commit**

```bash
git add src/data/db.py tests/test_db.py && git commit -m "add DuckDB storage layer"
```

---

### Task 5: BaseAgent + UniverseBuilder

**Files:**
- Create: `src/agents/base.py`
- Create: `src/agents/universe.py`
- Create: `tests/test_universe.py`

**Step 1: Write BaseAgent ABC**

```python
# src/agents/base.py
from abc import ABC, abstractmethod
from src.models.types import Stock, AgentScore
from src.data.provider import DataProvider

class BaseAgent(ABC):
    name: str
    weight: float

    @abstractmethod
    def score(self, universe: list[Stock], data: DataProvider, bars: dict) -> dict[str, AgentScore]:
        """Return {ticker: AgentScore}. bars = {ticker: pd.DataFrame}."""

    @abstractmethod
    def explain(self, ticker: str, score: AgentScore) -> str:
        """Human-readable explanation."""
```

Note: `bars` dict is passed in so agents don't each re-fetch data. Pipeline fetches once, distributes to all agents.

**Step 2: Write UniverseBuilder tests**

```python
# tests/test_universe.py
from src.agents.universe import UniverseBuilder
from src.models.types import Stock
from unittest.mock import MagicMock
import pandas as pd
from datetime import datetime

def test_filters_by_price_and_volume():
    provider = MagicMock()
    provider.get_assets.return_value = [
        Stock("AAPL", "Apple", "NASDAQ"),
        Stock("PENNY", "Penny Co", "OTC"),
        Stock("GOOD", "Good Co", "NYSE"),
    ]
    # AAPL: price $150, vol 1M — passes
    # PENNY: price $2, vol 100 — fails price + volume
    # GOOD: price $50, vol 800k — passes
    bars = {
        "AAPL": pd.DataFrame({"close": [150.0]*20, "volume": [1_000_000]*20}),
        "PENNY": pd.DataFrame({"close": [2.0]*20, "volume": [100]*20}),
        "GOOD": pd.DataFrame({"close": [50.0]*20, "volume": [800_000]*20}),
    }
    provider.get_bars.return_value = pd.concat([
        pd.DataFrame({"symbol": [t]*20, "close": bars[t]["close"], "volume": bars[t]["volume"],
                       "timestamp": pd.date_range("2026-01-01", periods=20)})
        for t in bars
    ])
    builder = UniverseBuilder(min_price=5.0, min_avg_volume=500_000)
    result = builder.build(provider)
    tickers = [s.ticker for s in result]
    assert "AAPL" in tickers
    assert "GOOD" in tickers
    assert "PENNY" not in tickers
```

**Step 3: Implement UniverseBuilder**

```python
# src/agents/universe.py
from datetime import datetime, timedelta
import pandas as pd
from src.models.types import Stock
from src.data.provider import DataProvider

EXCLUDE_EXCHANGES = {"OTC"}

class UniverseBuilder:
    def __init__(self, min_price: float = 5.0, min_avg_volume: int = 500_000):
        self.min_price = min_price
        self.min_avg_volume = min_avg_volume

    def build(self, provider: DataProvider) -> list[Stock]:
        all_assets = provider.get_assets()
        # Exclude OTC
        assets = [a for a in all_assets if a.exchange not in EXCLUDE_EXCHANGES]
        if not assets:
            return []

        tickers = [a.ticker for a in assets]
        end = datetime.now()
        start = end - timedelta(days=30)
        bars = provider.get_bars(tickers, start, end)

        if bars.empty:
            return []

        # Compute avg close price and avg volume per ticker
        stats = bars.groupby("symbol").agg(
            avg_close=("close", "mean"),
            avg_volume=("volume", "mean"),
        )

        passing = stats[
            (stats["avg_close"] >= self.min_price) &
            (stats["avg_volume"] >= self.min_avg_volume)
        ].index.tolist()

        asset_map = {a.ticker: a for a in assets}
        return [asset_map[t] for t in passing if t in asset_map]
```

**Step 4: Run tests — verify pass**

```bash
pytest tests/test_universe.py -v
```

**Step 5: Commit**

```bash
git add src/agents/base.py src/agents/universe.py tests/test_universe.py && git commit -m "add BaseAgent ABC and UniverseBuilder"
```

---

### Task 6: TrendAgent

**Files:**
- Create: `src/agents/trend.py`
- Create: `tests/test_trend.py`

**Step 1: Write tests**

```python
# tests/test_trend.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.agents.trend import TrendAgent
from src.models.types import Stock

def _make_uptrend_bars(days=252):
    """Simulate a stock in a steady uptrend."""
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    prices = 100 * (1 + np.cumsum(np.random.normal(0.001, 0.01, days)))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices,
        "volume": np.random.randint(500_000, 2_000_000, days),
    })

def _make_downtrend_bars(days=252):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    prices = 100 * (1 + np.cumsum(np.random.normal(-0.001, 0.01, days)))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 1.01, "high": prices * 1.02,
        "low": prices * 0.99, "close": prices,
        "volume": np.random.randint(500_000, 2_000_000, days),
    })

def test_uptrend_scores_higher_than_downtrend():
    agent = TrendAgent()
    stocks = [Stock("UP", "Up Co", "NYSE"), Stock("DOWN", "Down Co", "NYSE")]
    spy_bars = _make_uptrend_bars()
    bars = {"UP": _make_uptrend_bars(), "DOWN": _make_downtrend_bars(), "SPY": spy_bars}
    scores = agent.score(stocks, None, bars)
    assert scores["UP"].score > scores["DOWN"].score

def test_score_in_valid_range():
    agent = TrendAgent()
    stocks = [Stock("AAPL", "Apple", "NASDAQ")]
    bars = {"AAPL": _make_uptrend_bars(), "SPY": _make_uptrend_bars()}
    scores = agent.score(stocks, None, bars)
    assert 0 <= scores["AAPL"].score <= 100
```

**Step 2: Run tests — verify fail**

```bash
pytest tests/test_trend.py -v
```

**Step 3: Implement TrendAgent**

```python
# src/agents/trend.py
import numpy as np
import pandas as pd
from datetime import datetime
from src.agents.base import BaseAgent
from src.models.types import Stock, AgentScore
from src.data.provider import DataProvider

class TrendAgent(BaseAgent):
    name = "trend"
    weight = 0.35

    def score(self, universe: list[Stock], data: DataProvider, bars: dict) -> dict[str, AgentScore]:
        spy = bars.get("SPY")
        results = {}
        for stock in universe:
            df = bars.get(stock.ticker)
            if df is None or len(df) < 50:
                continue
            components = self._compute_components(df, spy)
            composite = (
                0.30 * components["momentum"] +
                0.20 * components["rel_strength"] +
                0.25 * components["trend_structure"] +
                0.15 * components["vol_contraction"] +
                0.10 * components["volume_confirm"]
            )
            results[stock.ticker] = AgentScore(
                ticker=stock.ticker, agent=self.name,
                score=np.clip(composite, 0, 100),
                confidence=min(len(df) / 252, 1.0),
                components=components, timestamp=datetime.now(),
            )
        return results

    def _compute_components(self, df: pd.DataFrame, spy: pd.DataFrame | None) -> dict:
        close = df["close"].values
        # Momentum: avg of 3m/6m/12m returns, scaled 0-100
        mom_3m = (close[-1] / close[-63] - 1) if len(close) >= 63 else 0
        mom_6m = (close[-1] / close[-126] - 1) if len(close) >= 126 else 0
        mom_12m = (close[-1] / close[-252] - 1) if len(close) >= 252 else mom_6m
        raw_mom = (mom_3m + mom_6m + mom_12m) / 3
        momentum = np.clip(50 + raw_mom * 200, 0, 100)  # center at 50, scale

        # Relative strength vs SPY
        rel_strength = 50.0
        if spy is not None and len(spy) >= 63:
            spy_ret = spy["close"].values[-1] / spy["close"].values[-63] - 1
            rel = mom_3m - spy_ret
            rel_strength = np.clip(50 + rel * 300, 0, 100)

        # Trend structure: price vs 20/50/200 SMA
        sma20 = np.mean(close[-20:]) if len(close) >= 20 else close[-1]
        sma50 = np.mean(close[-50:]) if len(close) >= 50 else close[-1]
        sma200 = np.mean(close[-200:]) if len(close) >= 200 else sma50
        above_count = (
            (1 if close[-1] > sma20 else 0) +
            (1 if close[-1] > sma50 else 0) +
            (1 if close[-1] > sma200 else 0) +
            (1 if sma20 > sma50 else 0) +
            (1 if sma50 > sma200 else 0)
        )
        trend_structure = above_count / 5 * 100

        # Volatility contraction: lower ATR% = tighter = better
        if len(df) >= 20:
            high = df["high"].values[-20:]
            low = df["low"].values[-20:]
            prev_close = df["close"].values[-21:-1] if len(df) >= 21 else close[-20:]
            tr = np.maximum(high - low, np.maximum(
                np.abs(high - prev_close), np.abs(low - prev_close)
            ))
            atr_pct = np.mean(tr) / close[-1] * 100
            vol_contraction = np.clip(100 - atr_pct * 20, 0, 100)
        else:
            vol_contraction = 50.0

        # Volume confirmation: up-day vol vs down-day vol
        if len(df) >= 20:
            recent = df.tail(20)
            up_days = recent[recent["close"] > recent["open"]]
            down_days = recent[recent["close"] <= recent["open"]]
            up_vol = up_days["volume"].mean() if len(up_days) > 0 else 1
            down_vol = down_days["volume"].mean() if len(down_days) > 0 else 1
            ratio = up_vol / max(down_vol, 1)
            volume_confirm = np.clip(ratio / 2 * 100, 0, 100)
        else:
            volume_confirm = 50.0

        return {
            "momentum": round(float(momentum), 1),
            "rel_strength": round(float(rel_strength), 1),
            "trend_structure": round(float(trend_structure), 1),
            "vol_contraction": round(float(vol_contraction), 1),
            "volume_confirm": round(float(volume_confirm), 1),
        }

    def explain(self, ticker: str, score: AgentScore) -> str:
        c = score.components
        parts = []
        if c["momentum"] > 65:
            parts.append("strong multi-timeframe momentum")
        elif c["momentum"] < 35:
            parts.append("weak/negative momentum")
        if c["trend_structure"] >= 80:
            parts.append("above all key SMAs")
        elif c["trend_structure"] <= 40:
            parts.append("below key SMAs")
        if c["vol_contraction"] > 70:
            parts.append("tight volatility (coiling)")
        if c["volume_confirm"] > 65:
            parts.append("volume confirming up moves")
        if c["rel_strength"] > 65:
            parts.append("outperforming SPY")
        elif c["rel_strength"] < 35:
            parts.append("underperforming SPY")
        summary = ", ".join(parts) if parts else "mixed signals"
        return f"{ticker} trend ({score.score:.0f}/100): {summary}"
```

**Step 4: Run tests — verify pass**

```bash
pytest tests/test_trend.py -v
```

**Step 5: Commit**

```bash
git add src/agents/trend.py tests/test_trend.py && git commit -m "add TrendAgent with momentum/structure/vol signals"
```

---

### Task 7: FundamentalsAgent (Stubbed)

**Files:**
- Create: `src/agents/fundamentals.py`
- Create: `tests/test_fundamentals.py`

**Step 1: Write test**

```python
# tests/test_fundamentals.py
from src.agents.fundamentals import FundamentalsAgent
from src.models.types import Stock

def test_stub_returns_neutral_scores():
    agent = FundamentalsAgent()
    stocks = [Stock("AAPL", "Apple", "NASDAQ"), Stock("MSFT", "Microsoft", "NASDAQ")]
    scores = agent.score(stocks, None, {})
    assert scores["AAPL"].score == 50.0
    assert scores["MSFT"].score == 50.0

def test_stub_explain():
    agent = FundamentalsAgent()
    stocks = [Stock("AAPL", "Apple", "NASDAQ")]
    scores = agent.score(stocks, None, {})
    explanation = agent.explain("AAPL", scores["AAPL"])
    assert "not yet available" in explanation.lower() or "stubbed" in explanation.lower()
```

**Step 2: Implement**

```python
# src/agents/fundamentals.py
from datetime import datetime
from src.agents.base import BaseAgent
from src.models.types import Stock, AgentScore
from src.data.provider import DataProvider

class FundamentalsAgent(BaseAgent):
    name = "fundamentals"
    weight = 0.25

    def score(self, universe: list[Stock], data: DataProvider, bars: dict) -> dict[str, AgentScore]:
        return {
            stock.ticker: AgentScore(
                ticker=stock.ticker, agent=self.name,
                score=50.0, confidence=0.0,
                components={"status": "stubbed"},
                timestamp=datetime.now(),
            )
            for stock in universe
        }

    def explain(self, ticker: str, score: AgentScore) -> str:
        return f"{ticker} fundamentals: stubbed — data not yet available (awaiting Massive integration)"
```

**Step 3: Run tests — verify pass, commit**

```bash
pytest tests/test_fundamentals.py -v
git add src/agents/fundamentals.py tests/test_fundamentals.py && git commit -m "add stubbed FundamentalsAgent"
```

---

### Task 8: SentimentAgent

**Files:**
- Create: `src/agents/sentiment.py`
- Create: `tests/test_sentiment.py`

**Step 1: Write tests**

```python
# tests/test_sentiment.py
from datetime import datetime, timedelta
from src.agents.sentiment import SentimentAgent, _keyword_sentiment
from src.models.types import Stock, NewsArticle

def test_keyword_sentiment_positive():
    assert _keyword_sentiment("Company beats earnings expectations, revenue surges") > 0

def test_keyword_sentiment_negative():
    assert _keyword_sentiment("Company misses estimates, stock plunges on weak guidance") < 0

def test_more_recent_news_scores_higher():
    agent = SentimentAgent()
    stocks = [Stock("HOT", "Hot Co", "NYSE"), Stock("COLD", "Cold Co", "NYSE")]
    now = datetime.now()
    news = {
        "HOT": [
            NewsArticle("HOT", "HOT beats earnings", "Reuters", now - timedelta(hours=2)),
            NewsArticle("HOT", "HOT revenue surges", "Bloomberg", now - timedelta(hours=5)),
            NewsArticle("HOT", "HOT raises guidance", "CNBC", now - timedelta(days=1)),
        ],
        "COLD": [
            NewsArticle("COLD", "COLD reports results", "Reuters", now - timedelta(days=25)),
        ],
    }
    scores = agent.score(stocks, None, {}, news=news)
    assert scores["HOT"].score > scores["COLD"].score
```

**Step 2: Implement**

```python
# src/agents/sentiment.py
import numpy as np
from datetime import datetime, timedelta
from src.agents.base import BaseAgent
from src.models.types import Stock, AgentScore, NewsArticle
from src.data.provider import DataProvider

POSITIVE_WORDS = {
    "beat", "beats", "surge", "surges", "record", "growth", "upgrade",
    "outperform", "raises", "strong", "bullish", "breakout", "momentum",
    "accelerat", "expan", "innovat", "exceed", "optimis", "positive",
}
NEGATIVE_WORDS = {
    "miss", "misses", "plunge", "decline", "downgrade", "weak", "bearish",
    "cut", "slash", "loss", "warn", "disappoint", "fall", "drops", "crash",
    "lawsuit", "investigat", "fraud", "deficit", "negativ",
}

def _keyword_sentiment(headline: str) -> float:
    words = headline.lower().split()
    pos = sum(1 for w in words for kw in POSITIVE_WORDS if kw in w)
    neg = sum(1 for w in words for kw in NEGATIVE_WORDS if kw in w)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total

class SentimentAgent(BaseAgent):
    name = "sentiment"
    weight = 0.20

    def score(self, universe: list[Stock], data: DataProvider, bars: dict,
              news: dict[str, list[NewsArticle]] | None = None) -> dict[str, AgentScore]:
        results = {}
        now = datetime.now()
        for stock in universe:
            articles = (news or {}).get(stock.ticker, [])
            components = self._compute_components(articles, now)
            composite = (
                0.40 * components["headline_sentiment"] +
                0.30 * components["news_volume"] +
                0.30 * components["news_recency"]
            )
            results[stock.ticker] = AgentScore(
                ticker=stock.ticker, agent=self.name,
                score=np.clip(composite, 0, 100),
                confidence=min(len(articles) / 10, 1.0),
                components=components, timestamp=now,
            )
        return results

    def _compute_components(self, articles: list[NewsArticle], now: datetime) -> dict:
        if not articles:
            return {"headline_sentiment": 50.0, "news_volume": 30.0, "news_recency": 30.0}

        # Headline sentiment: avg keyword score, scaled to 0-100
        sentiments = [_keyword_sentiment(a.headline) for a in articles]
        avg_sent = np.mean(sentiments)
        headline_sentiment = np.clip(50 + avg_sent * 50, 0, 100)

        # News volume: more articles in last 7 days = higher attention
        recent_7d = [a for a in articles if (now - a.published).days <= 7]
        news_volume = np.clip(len(recent_7d) / 5 * 100, 0, 100)

        # News recency: hours since most recent article
        most_recent = max(a.published for a in articles)
        hours_ago = (now - most_recent).total_seconds() / 3600
        news_recency = np.clip(100 - hours_ago * 2, 0, 100)

        return {
            "headline_sentiment": round(float(headline_sentiment), 1),
            "news_volume": round(float(news_volume), 1),
            "news_recency": round(float(news_recency), 1),
        }

    def explain(self, ticker: str, score: AgentScore) -> str:
        c = score.components
        parts = []
        if c["headline_sentiment"] > 65:
            parts.append("positive headline tone")
        elif c["headline_sentiment"] < 35:
            parts.append("negative headline tone")
        if c["news_volume"] > 60:
            parts.append("high news volume")
        elif c["news_volume"] < 30:
            parts.append("low news coverage")
        if c["news_recency"] > 70:
            parts.append("very recent coverage")
        summary = ", ".join(parts) if parts else "neutral/limited sentiment data"
        return f"{ticker} sentiment ({score.score:.0f}/100): {summary}"
```

**Step 3: Run tests — verify pass, commit**

```bash
pytest tests/test_sentiment.py -v
git add src/agents/sentiment.py tests/test_sentiment.py && git commit -m "add SentimentAgent with keyword scoring"
```

---

### Task 9: RiskAgent

**Files:**
- Create: `src/agents/risk.py`
- Create: `tests/test_risk.py`

**Step 1: Write tests**

```python
# tests/test_risk.py
import pandas as pd
import numpy as np
from datetime import datetime
from src.agents.risk import RiskAgent
from src.models.types import Stock

def _make_stable_bars(days=252):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    prices = 100 + np.cumsum(np.random.normal(0.05, 0.3, days))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 0.999, "high": prices * 1.005,
        "low": prices * 0.995, "close": prices, "volume": [2_000_000] * days,
    })

def _make_volatile_bars(days=252):
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    prices = 100 + np.cumsum(np.random.normal(0, 3, days))
    return pd.DataFrame({
        "timestamp": dates, "open": prices * 0.97, "high": prices * 1.05,
        "low": prices * 0.95, "close": prices, "volume": [100_000] * days,
    })

def test_stable_stock_scores_higher_risk():
    agent = RiskAgent()
    stocks = [Stock("SAFE", "Safe Co", "NYSE"), Stock("WILD", "Wild Co", "NYSE")]
    bars = {"SAFE": _make_stable_bars(), "WILD": _make_volatile_bars()}
    scores = agent.score(stocks, None, bars)
    assert scores["SAFE"].score > scores["WILD"].score

def test_risk_params_present():
    agent = RiskAgent()
    stocks = [Stock("AAPL", "Apple", "NASDAQ")]
    bars = {"AAPL": _make_stable_bars()}
    scores = agent.score(stocks, None, bars)
    assert "stop_loss" in scores["AAPL"].components
    assert "max_position_pct" in scores["AAPL"].components
```

**Step 2: Implement**

```python
# src/agents/risk.py
import numpy as np
import pandas as pd
from datetime import datetime
from src.agents.base import BaseAgent
from src.models.types import Stock, AgentScore
from src.data.provider import DataProvider

class RiskAgent(BaseAgent):
    name = "risk"
    weight = 0.10

    def score(self, universe: list[Stock], data: DataProvider, bars: dict) -> dict[str, AgentScore]:
        results = {}
        for stock in universe:
            df = bars.get(stock.ticker)
            if df is None or len(df) < 20:
                continue
            components = self._compute_components(df)
            composite = (
                0.30 * components["volatility_score"] +
                0.25 * components["drawdown_score"] +
                0.25 * components["liquidity_score"] +
                0.20 * components["distance_from_high"]
            )
            results[stock.ticker] = AgentScore(
                ticker=stock.ticker, agent=self.name,
                score=np.clip(composite, 0, 100),
                confidence=min(len(df) / 126, 1.0),
                components=components, timestamp=datetime.now(),
            )
        return results

    def _compute_components(self, df: pd.DataFrame) -> dict:
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values

        # Volatility: 20-day annualized, lower = better
        if len(close) >= 21:
            returns = np.diff(np.log(close[-21:]))
            annual_vol = np.std(returns) * np.sqrt(252) * 100
            volatility_score = np.clip(100 - annual_vol * 2, 0, 100)
        else:
            volatility_score = 50.0

        # Max drawdown over last 126 days (6 months), smaller = better
        lookback = min(len(close), 126)
        recent = close[-lookback:]
        peak = np.maximum.accumulate(recent)
        drawdowns = (recent - peak) / peak
        max_dd = abs(float(np.min(drawdowns))) * 100
        drawdown_score = np.clip(100 - max_dd * 3, 0, 100)

        # Liquidity: avg daily dollar volume
        avg_dollar_vol = np.mean(close[-20:] * df["volume"].values[-20:])
        # Scale: $10M+ = 100, $1M = 50, <$100k = 0
        liquidity_score = np.clip(np.log10(max(avg_dollar_vol, 1)) / 7 * 100, 0, 100)

        # Distance from 52-week high: closer = better
        high_52w = np.max(high[-min(len(high), 252):])
        dist_pct = (high_52w - close[-1]) / high_52w * 100
        distance_from_high = np.clip(100 - dist_pct * 3, 0, 100)

        # Risk params for output
        if len(df) >= 20:
            prev_close = close[-21:-1] if len(close) >= 21 else close[-20:]
            tr = np.maximum(high[-20:] - low[-20:], np.maximum(
                np.abs(high[-20:] - prev_close[-20:]), np.abs(low[-20:] - prev_close[-20:])
            ))
            atr = np.mean(tr)
            stop_loss = round(float(close[-1] - 2 * atr), 2)
        else:
            atr = close[-1] * 0.02
            stop_loss = round(float(close[-1] * 0.95), 2)

        # Position sizing: higher vol = smaller position
        max_position_pct = round(float(np.clip(20 - annual_vol * 0.3, 2, 15)), 1) if len(close) >= 21 else 5.0

        return {
            "volatility_score": round(float(volatility_score), 1),
            "drawdown_score": round(float(drawdown_score), 1),
            "liquidity_score": round(float(liquidity_score), 1),
            "distance_from_high": round(float(distance_from_high), 1),
            "stop_loss": stop_loss,
            "max_position_pct": max_position_pct,
            "annual_vol_pct": round(float(annual_vol) if len(close) >= 21 else 0, 1),
            "max_drawdown_pct": round(float(max_dd), 1),
        }

    def explain(self, ticker: str, score: AgentScore) -> str:
        c = score.components
        parts = []
        if c["volatility_score"] > 70:
            parts.append("low volatility")
        elif c["volatility_score"] < 30:
            parts.append(f"high volatility ({c['annual_vol_pct']:.0f}% ann.)")
        if c["drawdown_score"] < 40:
            parts.append(f"significant drawdown ({c['max_drawdown_pct']:.0f}%)")
        if c["distance_from_high"] > 80:
            parts.append("near 52-week highs")
        risk_line = f"Stop: ${c['stop_loss']}, max position: {c['max_position_pct']}%"
        summary = ", ".join(parts) if parts else "moderate risk profile"
        return f"{ticker} risk ({score.score:.0f}/100): {summary}. {risk_line}"
```

**Step 3: Run tests — verify pass, commit**

```bash
pytest tests/test_risk.py -v
git add src/agents/risk.py tests/test_risk.py && git commit -m "add RiskAgent with vol/drawdown/liquidity scoring"
```

---

### Task 10: RankingAgent

**Files:**
- Create: `src/agents/ranking.py`
- Create: `tests/test_ranking.py`

**Step 1: Write tests**

```python
# tests/test_ranking.py
from datetime import datetime
from src.agents.ranking import RankingAgent
from src.models.types import AgentScore, Stock

def _score(ticker, agent, value):
    return AgentScore(ticker=ticker, agent=agent, score=value,
                      confidence=0.9, components={}, timestamp=datetime.now())

def test_ranking_order():
    agent = RankingAgent()
    all_scores = {
        "trend": {"A": _score("A", "trend", 90), "B": _score("B", "trend", 40)},
        "fundamentals": {"A": _score("A", "fundamentals", 50), "B": _score("B", "fundamentals", 50)},
        "sentiment": {"A": _score("A", "sentiment", 70), "B": _score("B", "sentiment", 80)},
        "risk": {"A": _score("A", "risk", 80), "B": _score("B", "risk", 60)},
    }
    stocks = [Stock("A", "A Co", "NYSE", sector="Tech"), Stock("B", "B Co", "NYSE", sector="Health")]
    rankings = agent.rank(stocks, all_scores)
    assert rankings[0].ticker == "A"
    assert rankings[0].rank == 1

def test_sector_cap():
    agent = RankingAgent(sector_cap=2)
    # 4 tech stocks, 1 healthcare
    stocks = [
        Stock("T1", "", "NYSE", sector="Tech"), Stock("T2", "", "NYSE", sector="Tech"),
        Stock("T3", "", "NYSE", sector="Tech"), Stock("T4", "", "NYSE", sector="Tech"),
        Stock("H1", "", "NYSE", sector="Health"),
    ]
    all_scores = {}
    for agent_name in ["trend", "fundamentals", "sentiment", "risk"]:
        all_scores[agent_name] = {
            s.ticker: _score(s.ticker, agent_name, 80 - i)
            for i, s in enumerate(stocks)
        }
    rankings = agent.rank(stocks, all_scores, top_n=5)
    tech_count = sum(1 for r in rankings if r.scores.get("sector") == "Tech")
    assert tech_count <= 2
```

**Step 2: Implement**

```python
# src/agents/ranking.py
import numpy as np
from datetime import datetime
from src.models.types import Stock, AgentScore, Ranking
from collections import defaultdict

WEIGHTS = {
    "trend": 0.35,
    "fundamentals": 0.25,
    "sentiment": 0.20,
    "risk": 0.10,
}
# Remaining 0.10 is relative strength, embedded in trend's rel_strength component

class RankingAgent:
    def __init__(self, sector_cap: int = 3):
        self.sector_cap = sector_cap

    def rank(self, universe: list[Stock], all_scores: dict[str, dict[str, AgentScore]],
             top_n: int = 10) -> list[Ranking]:
        composites = []
        stock_map = {s.ticker: s for s in universe}

        for stock in universe:
            t = stock.ticker
            weighted_sum = 0.0
            total_weight = 0.0
            score_breakdown = {"sector": stock.sector}

            for agent_name, weight in WEIGHTS.items():
                agent_scores = all_scores.get(agent_name, {})
                if t in agent_scores:
                    weighted_sum += agent_scores[t].score * weight
                    total_weight += weight
                    score_breakdown[agent_name] = round(agent_scores[t].score, 1)

            if total_weight == 0:
                continue

            composite = weighted_sum / total_weight * total_weight / sum(WEIGHTS.values())
            # Normalize back to 0-100
            composite = weighted_sum / sum(WEIGHTS.values())

            risk_components = all_scores.get("risk", {}).get(t)
            risk_params = {}
            if risk_components:
                risk_params = {
                    "stop_loss": risk_components.components.get("stop_loss", 0),
                    "max_position_pct": risk_components.components.get("max_position_pct", 5),
                }

            composites.append({
                "ticker": t,
                "composite": round(float(composite), 1),
                "scores": score_breakdown,
                "risk_params": risk_params,
                "sector": stock.sector,
            })

        # Sort by composite descending
        composites.sort(key=lambda x: x["composite"], reverse=True)

        # Apply sector cap
        sector_counts = defaultdict(int)
        filtered = []
        for c in composites:
            sector = c["sector"]
            if sector and sector_counts[sector] >= self.sector_cap:
                continue
            sector_counts[sector] += 1
            filtered.append(c)
            if len(filtered) >= top_n:
                break

        return [
            Ranking(
                ticker=c["ticker"], rank=i + 1,
                composite=c["composite"], scores=c["scores"],
                explanation="", invalidation="",
                risk_params=c["risk_params"],
            )
            for i, c in enumerate(filtered)
        ]
```

**Step 3: Run tests — verify pass, commit**

```bash
pytest tests/test_ranking.py -v
git add src/agents/ranking.py tests/test_ranking.py && git commit -m "add RankingAgent with composite scoring and sector cap"
```

---

### Task 11: Output Formatters

**Files:**
- Create: `src/output/console.py`
- Create: `src/output/json_writer.py`
- Create: `tests/test_output.py`

**Step 1: Write tests**

```python
# tests/test_output.py
import json
from datetime import datetime
from pathlib import Path
from src.output.console import format_rankings
from src.output.json_writer import write_rankings
from src.models.types import Ranking

def _sample_rankings():
    return [
        Ranking("NVDA", 1, 82.3, {"trend": 91.2, "fundamentals": 50.0, "sentiment": 78.4, "risk": 89.1, "sector": "Technology"},
                "Strong momentum", "Break below 50 SMA", {"stop_loss": 142.5, "max_position_pct": 8.0}),
        Ranking("LLY", 2, 77.8, {"trend": 80.1, "fundamentals": 50.0, "sentiment": 71.2, "risk": 92.3, "sector": "Healthcare"},
                "Steady uptrend", "Loss of $700 support", {"stop_loss": 700.0, "max_position_pct": 10.0}),
    ]

def test_format_rankings_returns_string():
    output = format_rankings(_sample_rankings(), warnings=["Test warning"])
    assert "NVDA" in output
    assert "LLY" in output
    assert "Test warning" in output

def test_write_rankings_json(tmp_path):
    write_rankings(_sample_rankings(), [], str(tmp_path))
    files = list(tmp_path.glob("ranking-*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["rankings"][0]["ticker"] == "NVDA"
```

**Step 2: Implement console formatter**

```python
# src/output/console.py
from src.models.types import Ranking

AGENTS = ["trend", "fundamentals", "sentiment", "risk"]

def format_rankings(rankings: list[Ranking], warnings: list[str] | None = None) -> str:
    date = __import__("datetime").date.today().isoformat()
    lines = [f"\n{'='*60}", f"  Stock Rankings — {date}", f"{'='*60}\n"]

    header = f" {'#':>2}  {'Ticker':<6} {'Composite':>9}  {'Trend':>5}  {'Fund':>5}  {'Sent':>5}  {'Risk':>5}  {'Sector':<15}"
    lines.append(header)
    lines.append("-" * len(header))

    for r in rankings:
        line = (
            f" {r.rank:>2}  {r.ticker:<6} {r.composite:>9.1f}"
            f"  {r.scores.get('trend', 0):>5.1f}"
            f"  {r.scores.get('fundamentals', 0):>5.1f}"
            f"  {r.scores.get('sentiment', 0):>5.1f}"
            f"  {r.scores.get('risk', 0):>5.1f}"
            f"  {r.scores.get('sector', ''):<15}"
        )
        lines.append(line)

    if warnings:
        lines.append("")
        for w in warnings:
            lines.append(f"  ! {w}")

    lines.append("")
    for r in rankings:
        lines.append(f"-- {r.ticker} --")
        if r.explanation:
            lines.append(f"  Why now: {r.explanation}")
        if r.risk_params:
            lines.append(f"  Risk: Stop ${r.risk_params.get('stop_loss', '?')}, max {r.risk_params.get('max_position_pct', '?')}% portfolio")
        if r.invalidation:
            lines.append(f"  Invalidation: {r.invalidation}")
        lines.append("")

    return "\n".join(lines)
```

**Step 3: Implement JSON writer**

```python
# src/output/json_writer.py
import json
from datetime import date
from dataclasses import asdict
from pathlib import Path
from src.models.types import Ranking

def write_rankings(rankings: list[Ranking], warnings: list[str], output_dir: str = "output"):
    path = Path(output_dir)
    path.mkdir(exist_ok=True)
    today = date.today().isoformat()
    data = {
        "date": today,
        "rankings": [asdict(r) for r in rankings],
        "warnings": warnings,
    }
    filepath = path / f"ranking-{today}.json"
    filepath.write_text(json.dumps(data, indent=2, default=str))
    return str(filepath)
```

**Step 4: Run tests — verify pass, commit**

```bash
pytest tests/test_output.py -v
git add src/output/ tests/test_output.py && git commit -m "add console and JSON output formatters"
```

---

### Task 12: CLI Pipeline (run_ranking.py)

**Files:**
- Create: `run_ranking.py`

**Step 1: Implement the pipeline**

```python
#!/usr/bin/env python3
"""Trading Agent — Weekly Stock Ranking Pipeline."""
import os
import sys
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

from src.data.alpaca import AlpacaProvider
from src.data.db import Storage
from src.agents.universe import UniverseBuilder
from src.agents.trend import TrendAgent
from src.agents.fundamentals import FundamentalsAgent
from src.agents.sentiment import SentimentAgent
from src.agents.risk import RiskAgent
from src.agents.ranking import RankingAgent
from src.output.console import format_rankings
from src.output.json_writer import write_rankings

def main():
    load_dotenv()

    if not os.environ.get("ALPACA_API_KEY"):
        print("Error: Set ALPACA_API_KEY and ALPACA_SECRET in .env")
        sys.exit(1)

    print("Initializing...")
    provider = AlpacaProvider()
    db = Storage()

    # 1. Build universe
    print("Building universe...")
    builder = UniverseBuilder()
    universe = builder.build(provider)
    print(f"  {len(universe)} stocks in universe")

    if not universe:
        print("No stocks passed filters. Exiting.")
        return

    # 2. Fetch bars (1 year for trend calculations)
    print("Fetching price data...")
    tickers = [s.ticker for s in universe] + ["SPY", "QQQ"]
    end = datetime.now()
    start = end - timedelta(days=365)
    all_bars_df = provider.get_bars(tickers, start, end)

    # Organize bars by ticker
    bars = {}
    for ticker in tickers:
        mask = all_bars_df["symbol"] == ticker if "symbol" in all_bars_df.columns else False
        if hasattr(mask, "any") and mask.any():
            bars[ticker] = all_bars_df[mask].reset_index(drop=True)

    # Cache to DuckDB
    db.store_bars(all_bars_df.rename(columns={"symbol": "ticker"}) if "symbol" in all_bars_df.columns else all_bars_df)

    # 3. Fetch news for sentiment
    print("Fetching news...")
    news = {}
    for stock in universe[:50]:  # Limit to top 50 to avoid rate limits
        articles = provider.get_news([stock.ticker], end - timedelta(days=30), end)
        if articles:
            news[stock.ticker] = articles

    # 4. Score with agents (parallel where possible)
    print("Scoring...")
    trend_agent = TrendAgent()
    fundamentals_agent = FundamentalsAgent()
    sentiment_agent = SentimentAgent()
    risk_agent = RiskAgent()

    with ThreadPoolExecutor(max_workers=3) as executor:
        trend_future = executor.submit(trend_agent.score, universe, provider, bars)
        fund_future = executor.submit(fundamentals_agent.score, universe, provider, bars)
        sent_future = executor.submit(sentiment_agent.score, universe, provider, bars, news)

    trend_scores = trend_future.result()
    fund_scores = fund_future.result()
    sent_scores = sent_future.result()
    risk_scores = risk_agent.score(universe, provider, bars)

    all_scores = {
        "trend": trend_scores,
        "fundamentals": fund_scores,
        "sentiment": sent_scores,
        "risk": risk_scores,
    }

    # 5. Rank
    print("Ranking...")
    ranker = RankingAgent()
    rankings = ranker.rank(universe, all_scores)

    # Add explanations
    for r in rankings:
        parts = []
        if r.ticker in trend_scores:
            parts.append(trend_agent.explain(r.ticker, trend_scores[r.ticker]))
        if r.ticker in sent_scores:
            parts.append(sentiment_agent.explain(r.ticker, sent_scores[r.ticker]))
        if r.ticker in risk_scores:
            r.invalidation = risk_agent.explain(r.ticker, risk_scores[r.ticker])
        r.explanation = "; ".join(parts)

    # 6. Generate warnings
    warnings = _generate_warnings(rankings)

    # 7. Output
    print(format_rankings(rankings, warnings))
    filepath = write_rankings(rankings, warnings)
    print(f"Saved to {filepath}")

    # 8. Persist scores
    run_date = datetime.now()
    for agent_name, scores in all_scores.items():
        for ticker, s in scores.items():
            db.store_score(run_date, ticker, agent_name, s.score, s.confidence, s.components)

    db.close()
    print("Done.")

def _generate_warnings(rankings: list) -> list[str]:
    warnings = []
    from collections import Counter
    sectors = Counter(r.scores.get("sector", "") for r in rankings if r.scores.get("sector"))
    for sector, count in sectors.items():
        if count >= 3:
            warnings.append(f"Sector concentration: {count} picks in {sector}")
    return warnings

if __name__ == "__main__":
    main()
```

Note: add `python-dotenv` to pyproject.toml dependencies.

**Step 2: Commit**

```bash
git add run_ranking.py && git commit -m "add CLI pipeline entrypoint"
```

---

### Task 13: Claude Code Subagent Prompts

**Files:**
- Create: `.claude/agents/universe-researcher.md`
- Create: `.claude/agents/trend-analyst.md`
- Create: `.claude/agents/sentiment-analyst.md`
- Create: `.claude/agents/ranking-agent.md`

**Step 1: Write all subagent prompts**

See content in implementation — each prompt defines the agent's role, how it invokes the Python module, and how to interpret/present results.

**Step 2: Commit**

```bash
git add .claude/agents/ && git commit -m "add Claude Code subagent prompts"
```

---

### Task 14: Integration Test

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write end-to-end test with mock data**

Test the full pipeline from universe → scoring → ranking → output using synthetic data and mocked provider. Verifies all components wire together correctly.

**Step 2: Run full test suite**

```bash
pytest tests/ -v
```

**Step 3: Commit**

```bash
git add tests/test_integration.py && git commit -m "add integration test for full pipeline"
```
