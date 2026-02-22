# src/data/db.py
import duckdb
import json
import pandas as pd
from datetime import datetime

class Storage:
    def __init__(self, db_path: str = "data/trading_agent.duckdb"):
        self.conn = duckdb.connect(db_path)
        self._init_tables()

    def _init_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bars (
                symbol VARCHAR,
                timestamp TIMESTAMP,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                PRIMARY KEY (symbol, timestamp)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                run_date DATE,
                ticker VARCHAR,
                signal VARCHAR,
                score DOUBLE,
                confidence DOUBLE,
                components JSON,
                PRIMARY KEY (run_date, ticker, signal)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                run_date DATE,
                ticker VARCHAR,
                action VARCHAR,
                confidence DOUBLE,
                composite_score DOUBLE,
                signal_scores JSON,
                rationale VARCHAR,
                invalidation VARCHAR,
                risk_params JSON,
                PRIMARY KEY (run_date, ticker)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id VARCHAR PRIMARY KEY,
                parent_version VARCHAR,
                config_diff JSON,
                metrics JSON,
                decision VARCHAR,
                created_at TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS strategy_versions (
                version VARCHAR PRIMARY KEY,
                config_hash VARCHAR,
                promoted_date TIMESTAMP,
                metrics JSON
            )
        """)

    def store_bars(self, bars_df: pd.DataFrame):
        self.conn.execute(
            "INSERT OR REPLACE INTO bars SELECT * FROM bars_df"
        )

    def get_bars(self, tickers: list[str], start: datetime, end: datetime) -> pd.DataFrame:
        return self.conn.execute(
            "SELECT * FROM bars WHERE symbol IN (SELECT UNNEST(?)) AND timestamp >= ? AND timestamp < ? ORDER BY symbol, timestamp",
            [tickers, start, end]
        ).fetchdf()

    def store_score(self, run_date: datetime, ticker: str, signal: str,
                    score: float, confidence: float, components: dict):
        self.conn.execute(
            "INSERT OR REPLACE INTO scores VALUES (?, ?, ?, ?, ?, ?)",
            [run_date, ticker, signal, score, confidence, json.dumps(components)]
        )

    def get_scores(self, run_date: datetime) -> list[dict]:
        return self.conn.execute(
            "SELECT * FROM scores WHERE run_date = ?", [run_date]
        ).fetchdf().to_dict("records")

    def store_recommendation(self, run_date: datetime, rec: dict):
        self.conn.execute(
            "INSERT OR REPLACE INTO recommendations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [run_date, rec["ticker"], rec["action"], rec["confidence"],
             rec["composite_score"], json.dumps(rec.get("signal_scores", {})),
             rec.get("rationale", ""), rec.get("invalidation", ""),
             json.dumps(rec.get("risk_params", {}))]
        )

    def store_experiment(self, experiment_id: str, parent_version: str,
                         config_diff: dict, hypothesis: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO experiments VALUES (?, ?, ?, ?, ?, ?)",
            [experiment_id, parent_version, json.dumps(config_diff),
             None, None, datetime.now()]
        )

    def update_experiment_decision(self, experiment_id: str, decision: str, metrics: dict):
        self.conn.execute(
            "UPDATE experiments SET decision = ?, metrics = ? WHERE experiment_id = ?",
            [decision, json.dumps(metrics), experiment_id]
        )

    def get_experiment(self, experiment_id: str) -> dict | None:
        df = self.conn.execute(
            "SELECT * FROM experiments WHERE experiment_id = ?", [experiment_id]
        ).fetchdf()
        if df.empty:
            return None
        return df.to_dict("records")[0]

    def get_experiments(self) -> list[dict]:
        return self.conn.execute(
            "SELECT * FROM experiments ORDER BY created_at DESC"
        ).fetchdf().to_dict("records")

    def get_recent_experiments(self, limit: int = 10) -> list[dict]:
        return self.conn.execute(
            "SELECT * FROM experiments ORDER BY created_at DESC LIMIT ?", [limit]
        ).fetchdf().to_dict("records")

    def store_strategy_version(self, version: str, config_hash: str, metrics: dict):
        self.conn.execute(
            "INSERT OR REPLACE INTO strategy_versions VALUES (?, ?, ?, ?)",
            [version, config_hash, datetime.now(), json.dumps(metrics)]
        )

    def get_strategy_versions(self) -> list[dict]:
        return self.conn.execute(
            "SELECT * FROM strategy_versions ORDER BY promoted_date DESC"
        ).fetchdf().to_dict("records")

    def get_latest_strategy_version(self) -> dict | None:
        df = self.conn.execute(
            "SELECT * FROM strategy_versions ORDER BY promoted_date DESC LIMIT 1"
        ).fetchdf()
        if df.empty:
            return None
        return df.to_dict("records")[0]

    def close(self):
        self.conn.close()
