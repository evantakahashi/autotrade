# tests/test_m4_integration.py
"""Verify M4 components are wired up correctly."""
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import pytest
from src.data.db import Storage


@pytest.fixture
def populated_db(tmp_path):
    db_path = str(tmp_path / "test.duckdb")
    db = Storage(db_path)
    # Add experiments
    db.store_experiment("exp-001", "0.1", {"weights": {"trend": 0.40}}, "increase trend weight")
    db.update_experiment_decision("exp-001", "rejected", {"sharpe": 0.5})
    db.store_experiment("exp-002", "0.1", {"thresholds": {"buy": 75}}, "raise buy threshold")
    db.update_experiment_decision("exp-002", "promoted", {"sharpe": 1.2})
    # Add strategy version
    db.store_strategy_version("0.1", "abc123", {"sharpe": 0.8})
    db.store_strategy_version("0.2", "def456", {"sharpe": 1.1})
    # Add scores
    db.store_score(datetime(2026, 3, 1), "AAPL", "trend", 75.0, 0.8, {"momentum": 80})
    db.close()
    yield db_path


def test_query_all_subcommands(populated_db):
    """All 4 query.py subcommands return valid JSON."""
    commands = [
        [sys.executable, "query.py", "experiments", "--last", "5", "--db", populated_db],
        [sys.executable, "query.py", "experiment", "--id", "exp-001", "--db", populated_db],
        [sys.executable, "query.py", "strategy", "--current", "--db", populated_db],
        [sys.executable, "query.py", "strategy", "--history", "--db", populated_db],
        [sys.executable, "query.py", "scores", "--ticker", "AAPL", "--db", populated_db],
    ]
    for cmd in commands:
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0, f"{cmd} failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert data is not None


def test_agent_prompts_exist():
    """All 5 agent prompt files exist and are non-empty."""
    agents = [
        ".claude/agents/portfolio-analyst.md",
        ".claude/agents/risk-manager.md",
        ".claude/agents/signal-researcher.md",
        ".claude/agents/backtest-auditor.md",
        ".claude/agents/strategy-promoter.md",
    ]
    for path in agents:
        p = Path(path)
        assert p.exists(), f"Missing agent prompt: {path}"
        assert p.stat().st_size > 100, f"Agent prompt too short: {path}"


def test_memory_files_exist():
    """All 3 memory files exist."""
    files = [
        ".claude/memory/experiment-log.md",
        ".claude/memory/strategy-insights.md",
        ".claude/memory/known-issues.md",
    ]
    for path in files:
        assert Path(path).exists(), f"Missing memory file: {path}"


def test_hook_scripts_exist():
    """Hook helper scripts exist."""
    scripts = [
        "scripts/validate_experiment.py",
        "scripts/log_promotion.py",
    ]
    for path in scripts:
        assert Path(path).exists(), f"Missing hook script: {path}"
