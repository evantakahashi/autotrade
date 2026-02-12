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
