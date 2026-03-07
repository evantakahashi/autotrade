import json
from fastapi import APIRouter, HTTPException, Query
from src.api.deps import get_db

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


@router.get("")
def list_experiments(last: int = Query(default=10, ge=1, le=100)):
    db = get_db()
    experiments = db.get_recent_experiments(limit=last)
    results = []
    for exp in experiments:
        config_diff = exp.get("config_diff", "{}")
        if isinstance(config_diff, str):
            config_diff = json.loads(config_diff)
        metrics = exp.get("metrics", "{}")
        if isinstance(metrics, str):
            metrics = json.loads(metrics) if metrics else {}
        results.append({
            "experiment_id": exp["experiment_id"],
            "parent_version": exp.get("parent_version"),
            "config_diff": config_diff,
            "decision": exp.get("decision"),
            "metrics": metrics,
            "created_at": str(exp.get("created_at", "")),
        })
    return results


@router.get("/{experiment_id}")
def get_experiment(experiment_id: str):
    db = get_db()
    exp = db.get_experiment(experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found")

    config_diff = exp.get("config_diff", "{}")
    if isinstance(config_diff, str):
        config_diff = json.loads(config_diff)
    metrics = exp.get("metrics", "{}")
    if isinstance(metrics, str):
        metrics = json.loads(metrics) if metrics else {}

    return {
        "experiment_id": exp["experiment_id"],
        "parent_version": exp.get("parent_version"),
        "config_diff": config_diff,
        "decision": exp.get("decision"),
        "metrics": metrics,
        "created_at": str(exp.get("created_at", "")),
    }


@router.get("/{experiment_id}/paper-trades")
def get_paper_trades(experiment_id: str):
    db = get_db()
    trades = db.get_paper_trades(experiment_id)
    return [
        {
            "experiment_id": t["experiment_id"],
            "trade_date": str(t["trade_date"]),
            "baseline_return": t["baseline_return"],
            "experiment_return": t["experiment_return"],
            "baseline_cumulative": t["baseline_cumulative"],
            "experiment_cumulative": t["experiment_cumulative"],
        }
        for t in trades
    ]
