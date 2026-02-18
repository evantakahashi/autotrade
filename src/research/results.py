# src/research/results.py
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class WindowResult:
    window_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    metrics: dict = field(default_factory=dict)
    positions: dict = field(default_factory=dict)

@dataclass
class BacktestResult:
    strategy_version: str
    window_results: list[WindowResult] = field(default_factory=list)
    aggregate_metrics: dict = field(default_factory=dict)
    config_snapshot: dict = field(default_factory=dict)

    def windows_passing(self, condition: Callable[[dict], bool]) -> int:
        return sum(1 for w in self.window_results if condition(w.metrics))
