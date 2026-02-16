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
