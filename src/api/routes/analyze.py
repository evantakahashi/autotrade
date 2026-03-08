from datetime import datetime, timedelta
from dataclasses import asdict
from fastapi import APIRouter
from pydantic import BaseModel
from src.data.alpaca import AlpacaProvider
from src.agents.portfolio_analyst import PortfolioAnalyst
from src.agents.risk_manager import RiskManager
from src.strategy.config import load_strategy
from src.api.deps import get_strategies_dir

router = APIRouter(prefix="/api", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    tickers: list[str]
    days: int = 365


@router.post("/analyze")
def run_analysis(req: AnalyzeRequest):
    strategies_dir = get_strategies_dir()
    from src.api.deps import get_db
    db = get_db()
    latest = db.get_latest_strategy_version()
    if latest:
        version = latest["version"]
        config_path = f"{strategies_dir}/v{version}.yaml"
    else:
        config_path = f"{strategies_dir}/v0.1.yaml"

    config = load_strategy(config_path)
    provider = AlpacaProvider()

    tickers = [t.upper().strip() for t in req.tickers]
    all_tickers = tickers + ["SPY"]
    end = datetime.now()
    start = end - timedelta(days=req.days)

    all_bars_df = provider.get_bars(all_tickers, start, end)
    if all_bars_df.empty:
        return {"recommendations": [], "warnings": ["No data returned. Check tickers."]}

    bars = {}
    for ticker in all_tickers:
        mask = all_bars_df["symbol"] == ticker
        if mask.any():
            bars[ticker] = all_bars_df[mask].sort_values("timestamp").reset_index(drop=True)

    analyst = PortfolioAnalyst(config)
    recommendations = analyst.analyze(tickers, bars)

    risk_mgr = RiskManager()
    warnings = risk_mgr.review(recommendations, thresholds=config.thresholds)

    return {
        "strategy_version": config.version,
        "date": datetime.now().isoformat(),
        "recommendations": [asdict(r) for r in recommendations],
        "warnings": warnings,
    }
