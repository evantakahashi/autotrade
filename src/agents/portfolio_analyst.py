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
