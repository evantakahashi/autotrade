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
