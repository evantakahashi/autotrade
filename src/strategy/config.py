# src/strategy/config.py
from dataclasses import dataclass, field
import yaml

@dataclass
class BacktestConfig:
    train_months: int = 6
    validation_months: int = 2
    test_months: int = 1
    step_months: int = 1
    rebalance_frequency: str = "weekly"  # "weekly" or "monthly"
    transaction_cost_bps: float = 10.0   # basis points per trade

@dataclass
class StrategyConfig:
    version: str
    name: str
    weights: dict[str, float]
    thresholds: dict[str, float]
    filters: dict[str, float] = field(default_factory=dict)
    overrides: str | None = None
    backtest: BacktestConfig = field(default_factory=BacktestConfig)

def load_strategy(path: str) -> StrategyConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)

    bt_raw = raw.get("backtest", {})
    backtest = BacktestConfig(
        train_months=bt_raw.get("train_months", 6),
        validation_months=bt_raw.get("validation_months", 2),
        test_months=bt_raw.get("test_months", 1),
        step_months=bt_raw.get("step_months", 1),
        rebalance_frequency=bt_raw.get("rebalance_frequency", "weekly"),
        transaction_cost_bps=bt_raw.get("transaction_cost_bps", 10.0),
    )

    config = StrategyConfig(
        version=str(raw["version"]),
        name=raw["name"],
        weights=raw["weights"],
        thresholds=raw["thresholds"],
        filters=raw.get("filters", {}),
        overrides=raw.get("overrides"),
        backtest=backtest,
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
