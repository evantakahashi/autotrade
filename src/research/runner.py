# src/research/runner.py
from datetime import datetime
import pandas as pd
from src.strategy.config import StrategyConfig
from src.agents.portfolio_analyst import PortfolioAnalyst

class StrategyRunner:
    """Wraps PortfolioAnalyst for historical simulation. No lookahead."""

    def __init__(self, config: StrategyConfig):
        self.config = config
        self.analyst = PortfolioAnalyst(config)

    def get_positions(
        self,
        tickers: list[str],
        bars: dict[str, pd.DataFrame],
        as_of: datetime,
    ) -> dict[str, dict]:
        """Run the strategy as if 'as_of' is today. Returns {ticker: {action, composite_score}}."""
        # Truncate bars to as_of date -- prevents lookahead
        truncated = {}
        for ticker, df in bars.items():
            mask = df["timestamp"] <= pd.Timestamp(as_of)
            truncated_df = df[mask].copy()
            if len(truncated_df) >= 20:
                truncated[ticker] = truncated_df

        recs = self.analyst.analyze(tickers, truncated)
        return {
            r.ticker: {
                "action": r.action,
                "composite_score": r.composite_score,
                "signal_scores": r.signal_scores,
            }
            for r in recs
        }
