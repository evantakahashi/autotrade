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
