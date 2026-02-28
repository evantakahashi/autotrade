#!/usr/bin/env python3
"""Log a strategy promotion to memory.

Hook intent: run as a PostToolUse hook on Write when path matches strategies/v*.yaml.
Example hook config in .claude/settings.json:
  "PostToolUse" matcher "Write" -> "python scripts/log_promotion.py"
"""
import json
from datetime import datetime
from src.data.db import Storage

db = Storage()
latest = db.get_latest_strategy_version()
db.close()
if latest:
    metrics = latest.get("metrics", {})
    if isinstance(metrics, str):
        metrics = json.loads(metrics)
    sharpe = metrics.get("sharpe", "?")
    entry = f"- **{latest['version']}** promoted {datetime.now().strftime('%Y-%m-%d')} — Sharpe: {sharpe}\n"
    memory_path = ".claude/memory/experiment-log.md"
    with open(memory_path, "a") as f:
        f.write(entry)
    print(f"Logged promotion: {latest['version']}")
