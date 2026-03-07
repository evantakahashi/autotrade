import json
import yaml
from pathlib import Path
from fastapi import APIRouter
from src.api.deps import get_db, get_strategies_dir

router = APIRouter(prefix="/api/strategy", tags=["strategy"])


@router.get("/current")
def get_current_strategy():
    db = get_db()
    latest = db.get_latest_strategy_version()
    if latest is None:
        return {"error": "No strategy versions found"}

    version = latest["version"]
    strategies_dir = get_strategies_dir()
    config_path = Path(strategies_dir) / f"v{version}.yaml"

    config = {}
    if config_path.exists():
        config = yaml.safe_load(config_path.read_text())

    metrics = latest.get("metrics", "{}")
    if isinstance(metrics, str):
        metrics = json.loads(metrics)

    return {
        "version": version,
        "config_hash": latest.get("config_hash"),
        "promoted_date": str(latest.get("promoted_date", "")),
        "weights": config.get("weights", {}),
        "thresholds": config.get("thresholds", {}),
        "filters": config.get("filters", {}),
        "metrics": metrics,
    }


@router.get("/history")
def get_strategy_history():
    db = get_db()
    versions = db.get_strategy_versions()
    results = []
    for v in versions:
        metrics = v.get("metrics", "{}")
        if isinstance(metrics, str):
            metrics = json.loads(metrics)
        results.append({
            "version": v["version"],
            "config_hash": v.get("config_hash"),
            "promoted_date": str(v.get("promoted_date", "")),
            "metrics": metrics,
        })
    return results
