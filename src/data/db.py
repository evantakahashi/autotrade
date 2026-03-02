# src/data/db.py
import duckdb
import json
import pandas as pd
from datetime import date, datetime

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
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS paper_trades (
                experiment_id VARCHAR,
                trade_date DATE,
                baseline_positions JSON,
                experiment_positions JSON,
                baseline_return DOUBLE,
                experiment_return DOUBLE,
                baseline_cumulative DOUBLE,
                experiment_cumulative DOUBLE,
                PRIMARY KEY (experiment_id, trade_date)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS loop_state (
                loop_id VARCHAR PRIMARY KEY DEFAULT 'main',
                status VARCHAR,
                paper_trading_experiment VARCHAR,
                paper_start_date DATE,
                last_iteration_at TIMESTAMP,
                consecutive_rejections INTEGER DEFAULT 0
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

    def store_paper_trade(self, experiment_id: str, trade_date, baseline_positions: dict,
                          experiment_positions: dict, baseline_return: float,
                          experiment_return: float, baseline_cumulative: float,
                          experiment_cumulative: float):
        self.conn.execute(
            "INSERT OR REPLACE INTO paper_trades VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [experiment_id, trade_date, json.dumps(baseline_positions),
             json.dumps(experiment_positions), baseline_return, experiment_return,
             baseline_cumulative, experiment_cumulative]
        )

    def get_paper_trades(self, experiment_id: str) -> list[dict]:
        df = self.conn.execute(
            "SELECT * FROM paper_trades WHERE experiment_id = ? ORDER BY trade_date",
            [experiment_id]
        ).fetchdf()
        if df.empty:
            return []
        return df.to_dict("records")

    def get_paper_trade_count(self, experiment_id: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM paper_trades WHERE experiment_id = ?",
            [experiment_id]
        ).fetchone()[0]

    def save_loop_state(self, status: str, paper_trading_experiment: str | None = None,
                        paper_start_date=None, consecutive_rejections: int = 0):
        self.conn.execute(
            """INSERT OR REPLACE INTO loop_state
               VALUES ('main', ?, ?, ?, ?, ?)""",
            [status, paper_trading_experiment, paper_start_date,
             datetime.now(), consecutive_rejections]
        )

    def get_loop_state(self) -> dict | None:
        df = self.conn.execute(
            "SELECT * FROM loop_state WHERE loop_id = 'main'"
        ).fetchdf()
        if df.empty:
            return None
        return df.to_dict("records")[0]

    def invalidate_inflight_experiments(self, exclude_id: str | None = None):
        if exclude_id:
            self.conn.execute(
                "UPDATE experiments SET decision = 'invalidated' WHERE decision IS NULL AND experiment_id != ?",
                [exclude_id]
            )
        else:
            self.conn.execute(
                "UPDATE experiments SET decision = 'invalidated' WHERE decision IS NULL"
            )

    def close(self):
        self.conn.close()
