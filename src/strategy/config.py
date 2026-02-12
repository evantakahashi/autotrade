# src/strategy/config.py
from dataclasses import dataclass, field
import yaml

@dataclass
class StrategyConfig:
    version: str
    name: str
    weights: dict[str, float]
    thresholds: dict[str, float]
    filters: dict[str, float] = field(default_factory=dict)
    overrides: str | None = None

def load_strategy(path: str) -> StrategyConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)

    config = StrategyConfig(
        version=str(raw["version"]),
        name=raw["name"],
        weights=raw["weights"],
        thresholds=raw["thresholds"],
        filters=raw.get("filters", {}),
        overrides=raw.get("overrides"),
    )
    _validate(config)
    return config

def _validate(config: StrategyConfig):
    # Weights must sum to ~1.0
    total = sum(config.weights.values())
    if abs(total - 1.0) > 0.01:
        raise ValueError(f"Weights must sum to 1.0, got {total}")

    # Buy threshold must be above sell
    if config.thresholds.get("buy", 0) <= config.thresholds.get("sell", 0):
        raise ValueError("Buy threshold must be above sell threshold")
