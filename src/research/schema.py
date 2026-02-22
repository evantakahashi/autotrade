# src/research/schema.py
import copy

BOUNDS = {
    "weights": {"min": 0.0, "max": 0.5},
    "thresholds": {
        "buy": {"min": 50, "max": 90},
        "sell": {"min": 20, "max": 60},
    },
    "filters": {
        "min_price": {"min": 1.0, "max": 50.0},
        "min_avg_volume": {"min": 100_000, "max": 5_000_000},
        "max_annual_volatility": {"min": 20, "max": 200},
    },
}

def validate_config_diff(baseline: dict, diff: dict) -> list[str]:
    """Validate a proposed config diff against schema bounds. Returns list of error strings."""
    errors = []
    merged = apply_diff(baseline, diff)

    # Validate weights
    if "weights" in merged:
        for name, val in merged["weights"].items():
            if val < BOUNDS["weights"]["min"] or val > BOUNDS["weights"]["max"]:
                errors.append(f"Weight '{name}' = {val} outside bounds [{BOUNDS['weights']['min']}, {BOUNDS['weights']['max']}]")
        total = sum(merged["weights"].values())
        if abs(total - 1.0) > 0.01:
            errors.append(f"Weights sum to {total:.3f}, must sum to 1.0")

    # Validate thresholds
    if "thresholds" in merged:
        for name, val in merged["thresholds"].items():
            if name in BOUNDS["thresholds"]:
                bounds = BOUNDS["thresholds"][name]
                if val < bounds["min"] or val > bounds["max"]:
                    errors.append(f"Threshold '{name}' = {val} outside bounds [{bounds['min']}, {bounds['max']}]")
        buy = merged["thresholds"].get("buy", 70)
        sell = merged["thresholds"].get("sell", 40)
        if buy <= sell:
            errors.append(f"Buy threshold ({buy}) must be above sell threshold ({sell})")

    # Validate filters
    if "filters" in merged:
        for name, val in merged["filters"].items():
            if name in BOUNDS["filters"]:
                bounds = BOUNDS["filters"][name]
                if val < bounds["min"] or val > bounds["max"]:
                    errors.append(f"Filter '{name}' = {val} outside bounds [{bounds['min']}, {bounds['max']}]")

    return errors

def apply_diff(baseline: dict, diff: dict) -> dict:
    """Deep merge diff into baseline. Returns new dict."""
    merged = copy.deepcopy(baseline)
    for key, val in diff.items():
        if isinstance(val, dict) and key in merged and isinstance(merged[key], dict):
            merged[key].update(val)
        else:
            merged[key] = val
    return merged
