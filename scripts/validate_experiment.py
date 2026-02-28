#!/usr/bin/env python3
"""Validate an experiment config against schema bounds.

Hook intent: run as a PostToolUse hook on Write when path matches experiments/*/config.yaml.
Example hook config in .claude/settings.json:
  "PostToolUse" matcher "Write" -> "python scripts/validate_experiment.py <file>"
"""
import sys
import yaml
from src.research.schema import validate_config_diff
from src.strategy.config import load_strategy

if len(sys.argv) < 2:
    print("Usage: validate_experiment.py <config.yaml>")
    sys.exit(1)

baseline = load_strategy("strategies/v0.1.yaml")
baseline_dict = {"weights": baseline.weights, "thresholds": baseline.thresholds, "filters": baseline.filters}
diff = yaml.safe_load(open(sys.argv[1]))
errors = validate_config_diff(baseline_dict, diff)
if errors:
    print(f"WARN: Schema validation errors: {errors}")
else:
    print("Config valid")
