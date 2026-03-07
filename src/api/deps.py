from src.data.db import Storage

_db: Storage | None = None
_db_path: str = "data/trading_agent.duckdb"
_strategies_dir: str = "strategies"


def configure(db_path: str, strategies_dir: str):
    global _db_path, _strategies_dir, _db
    _db_path = db_path
    _strategies_dir = strategies_dir
    _db = None


def get_db() -> Storage:
    global _db
    if _db is None:
        _db = Storage(_db_path)
    return _db


def get_strategies_dir() -> str:
    return _strategies_dir
