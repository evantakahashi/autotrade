# tests/test_schema.py
import pytest
from src.research.schema import validate_config_diff, apply_diff, BOUNDS

def test_valid_weight_change():
    baseline = {"weights": {"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                            "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
                "thresholds": {"buy": 70, "sell": 40}, "filters": {}}
    diff = {"weights": {"trend": 0.40, "fundamentals": 0.15}}
    errors = validate_config_diff(baseline, diff)
    assert len(errors) == 0

def test_weight_exceeds_max():
    baseline = {"weights": {"trend": 0.35}, "thresholds": {"buy": 70, "sell": 40}, "filters": {}}
    diff = {"weights": {"trend": 0.60}}  # max 0.5
    errors = validate_config_diff(baseline, diff)
    assert any("trend" in e for e in errors)

def test_weights_dont_sum_to_one():
    baseline = {"weights": {"trend": 0.35, "relative_strength": 0.10, "volatility": 0.15,
                            "liquidity": 0.10, "fundamentals": 0.20, "sentiment": 0.10},
                "thresholds": {"buy": 70, "sell": 40}, "filters": {}}
    diff = {"weights": {"trend": 0.50}}  # now sums to 1.15
    errors = validate_config_diff(baseline, diff)
    assert any("sum" in e.lower() for e in errors)

def test_threshold_out_of_range():
    baseline = {"weights": {"trend": 1.0}, "thresholds": {"buy": 70, "sell": 40}, "filters": {}}
    diff = {"thresholds": {"buy": 95}}  # max 90
    errors = validate_config_diff(baseline, diff)
    assert len(errors) > 0

def test_buy_below_sell():
    baseline = {"weights": {"trend": 1.0}, "thresholds": {"buy": 70, "sell": 40}, "filters": {}}
    diff = {"thresholds": {"buy": 35}}  # below sell
    errors = validate_config_diff(baseline, diff)
    assert any("buy" in e.lower() and "sell" in e.lower() for e in errors)

def test_apply_diff():
    baseline = {"weights": {"trend": 0.35, "volatility": 0.15},
                "thresholds": {"buy": 70, "sell": 40}, "filters": {}}
    diff = {"weights": {"trend": 0.40}, "thresholds": {"sell": 35}}
    merged = apply_diff(baseline, diff)
    assert merged["weights"]["trend"] == 0.40
    assert merged["weights"]["volatility"] == 0.15  # unchanged
    assert merged["thresholds"]["sell"] == 35
    assert merged["thresholds"]["buy"] == 70  # unchanged
