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
