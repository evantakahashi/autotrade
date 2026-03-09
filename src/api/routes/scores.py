import json
from fastapi import APIRouter, Query
from src.api.deps import get_db

router = APIRouter(prefix="/api/scores", tags=["scores"])


@router.get("/{ticker}")
def get_scores(ticker: str, last: int = Query(default=10, ge=1, le=100)):
    db = get_db()
    rows = db.conn.execute(
        "SELECT * FROM scores WHERE ticker = ? ORDER BY run_date DESC LIMIT ?",
        [ticker.upper(), last]
    ).fetchdf().to_dict("records")

    results = []
    for r in rows:
        components = r.get("components", "{}")
        if isinstance(components, str):
            components = json.loads(components)
        results.append({
            "run_date": str(r["run_date"]),
            "ticker": r["ticker"],
            "signal": r["signal"],
            "score": r["score"],
            "confidence": r["confidence"],
            "components": components,
        })
    return results
