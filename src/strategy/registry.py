# src/strategy/registry.py
import hashlib
import yaml
from pathlib import Path
from src.data.db import Storage
from src.research.schema import apply_diff

class StrategyRegistry:
    def __init__(self, db: Storage, strategies_dir: str = "strategies"):
        self.db = db
        self.strategies_dir = Path(strategies_dir)

    def promote(self, parent_version: str, config_diff: dict, metrics: dict) -> str:
        # Load parent config
        parent_path = self.strategies_dir / f"v{parent_version}.yaml"
        parent_config = yaml.safe_load(parent_path.read_text())

        # Merge diff
        merged = apply_diff(parent_config, config_diff)

        # Bump version
        new_version = self._next_version(parent_version)
        merged["version"] = new_version
        merged["name"] = f"promoted-from-{parent_version}"

        # Write new config
        new_path = self.strategies_dir / f"v{new_version}.yaml"
        new_path.write_text(yaml.dump(merged, default_flow_style=False, sort_keys=False))

        # Record in DB
        config_hash = hashlib.sha256(yaml.dump(merged).encode()).hexdigest()[:12]
        self.db.store_strategy_version(new_version, config_hash, metrics)

        return new_version

    def get_current_version(self) -> str:
        # Check DB for latest promoted version
        latest = self.db.get_latest_strategy_version()
        if latest:
            return latest["version"]
        # Fallback: find highest version file
        versions = sorted(self.strategies_dir.glob("v*.yaml"))
        if versions:
            name = versions[-1].stem  # e.g. "v0.1"
            return name[1:]  # strip "v"
        return "0.1"

    def get_current_config_path(self) -> str:
        version = self.get_current_version()
        return str(self.strategies_dir / f"v{version}.yaml")

    def _next_version(self, parent: str) -> str:
        parts = parent.split(".")
        if len(parts) == 2:
            major, minor = int(parts[0]), int(parts[1])
            return f"{major}.{minor + 1}"
        return f"{parent}.1"
