# tests/test_registry.py
import yaml
from pathlib import Path
from src.strategy.registry import StrategyRegistry
from src.data.db import Storage

def test_promote_creates_new_version(tmp_path):
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir()
    # Create baseline
    baseline = {
        "version": "0.1", "name": "baseline",
        "weights": {"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                     "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
        "thresholds": {"buy": 70, "hold_min": 40, "sell": 40},
        "filters": {}, "backtest": {},
    }
    (strategies_dir / "v0.1.yaml").write_text(yaml.dump(baseline))

    db = Storage(str(tmp_path / "test.duckdb"))
    registry = StrategyRegistry(db, str(strategies_dir))

    new_version = registry.promote(
        parent_version="0.1",
        config_diff={"weights": {"trend": 0.40, "fundamentals": 0.15}},
        metrics={"sharpe": 1.3},
    )
    assert new_version == "0.2"
    assert (strategies_dir / "v0.2.yaml").exists()

    # Verify merged config
    new_config = yaml.safe_load((strategies_dir / "v0.2.yaml").read_text())
    assert new_config["weights"]["trend"] == 0.40
    assert new_config["weights"]["relative_strength"] == 0.10  # unchanged
    assert new_config["version"] == "0.2"

def test_get_current_version(tmp_path):
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir()
    config = {"version": "0.1", "name": "baseline", "weights": {"trend": 1.0},
              "thresholds": {"buy": 70, "sell": 40}, "filters": {}, "backtest": {}}
    (strategies_dir / "v0.1.yaml").write_text(yaml.dump(config))

    db = Storage(str(tmp_path / "test.duckdb"))
    registry = StrategyRegistry(db, str(strategies_dir))
    assert registry.get_current_version() == "0.1"

def test_sequential_version_bumps(tmp_path):
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir()
    config = {"version": "0.1", "name": "baseline", "weights": {"trend": 0.5, "volatility": 0.5},
              "thresholds": {"buy": 70, "sell": 40}, "filters": {}, "backtest": {}}
    (strategies_dir / "v0.1.yaml").write_text(yaml.dump(config))

    db = Storage(str(tmp_path / "test.duckdb"))
    registry = StrategyRegistry(db, str(strategies_dir))
    v1 = registry.promote("0.1", {"weights": {"trend": 0.45, "volatility": 0.55}}, {})
    v2 = registry.promote(v1, {"weights": {"trend": 0.40, "volatility": 0.60}}, {})
    assert v1 == "0.2"
    assert v2 == "0.3"
