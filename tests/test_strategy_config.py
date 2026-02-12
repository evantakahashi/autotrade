# tests/test_strategy_config.py
from pathlib import Path
from src.strategy.config import StrategyConfig, load_strategy

def test_load_strategy_from_yaml(tmp_path):
    yaml_content = """
version: "0.1"
name: "test-baseline"
weights:
  trend: 0.35
  relative_strength: 0.10
  volatility: 0.15
  liquidity: 0.10
  fundamentals: 0.20
  sentiment: 0.10
thresholds:
  buy: 70
  hold_min: 40
  sell: 40
filters:
  min_price: 5.0
  min_avg_volume: 500000
  max_annual_volatility: 100
"""
    config_file = tmp_path / "test.yaml"
    config_file.write_text(yaml_content)
    config = load_strategy(str(config_file))
    assert config.version == "0.1"
    assert config.weights["trend"] == 0.35
    assert sum(config.weights.values()) == pytest.approx(1.0)
    assert config.thresholds["buy"] == 70

def test_weights_must_sum_to_one(tmp_path):
    yaml_content = """
version: "0.1"
name: "bad"
weights:
  trend: 0.5
  relative_strength: 0.9
thresholds:
  buy: 70
  hold_min: 40
  sell: 40
filters: {}
"""
    config_file = tmp_path / "bad.yaml"
    config_file.write_text(yaml_content)
    with pytest.raises(ValueError, match="[Ww]eights"):
        load_strategy(str(config_file))

def test_thresholds_buy_above_sell(tmp_path):
    yaml_content = """
version: "0.1"
name: "bad"
weights:
  trend: 1.0
thresholds:
  buy: 30
  hold_min: 40
  sell: 70
filters: {}
"""
    config_file = tmp_path / "bad.yaml"
    config_file.write_text(yaml_content)
    with pytest.raises(ValueError, match="[Tt]hreshold"):
        load_strategy(str(config_file))

import pytest
