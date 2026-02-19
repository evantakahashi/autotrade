# tests/test_windows.py
from datetime import date
from src.research.windows import generate_windows
from src.strategy.config import BacktestConfig

def test_generates_correct_number_of_windows():
    # 24 months of data, 6m train + 2m val + 1m test = 9m, step 1m
    # First window needs 9 months, leaves 15 months for stepping = ~15 windows
    config = BacktestConfig(train_months=6, validation_months=2,
                            test_months=1, step_months=1)
    windows = generate_windows(
        data_start=date(2024, 1, 1),
        data_end=date(2026, 1, 1),
        config=config,
    )
    assert len(windows) > 10
    assert len(windows) < 20

def test_window_dates_non_overlapping_test():
    config = BacktestConfig(train_months=6, validation_months=2,
                            test_months=1, step_months=1)
    windows = generate_windows(date(2024, 1, 1), date(2026, 1, 1), config)
    # Test periods should step forward by step_months
    for i in range(1, len(windows)):
        assert windows[i]["test_start"] > windows[i-1]["test_start"]

def test_no_lookahead():
    config = BacktestConfig(train_months=6, validation_months=2,
                            test_months=1, step_months=1)
    windows = generate_windows(date(2024, 1, 1), date(2026, 1, 1), config)
    for w in windows:
        assert w["train_end"] <= w["validation_start"]
        assert w["validation_end"] <= w["test_start"]
        assert w["test_end"] <= date(2026, 1, 1)

def test_window_structure():
    config = BacktestConfig(train_months=6, validation_months=2,
                            test_months=1, step_months=1)
    windows = generate_windows(date(2024, 1, 1), date(2025, 6, 1), config)
    w = windows[0]
    required_keys = {"train_start", "train_end", "validation_start",
                     "validation_end", "test_start", "test_end", "window_id"}
    assert required_keys.issubset(set(w.keys()))

def test_insufficient_data_returns_empty():
    config = BacktestConfig(train_months=6, validation_months=2,
                            test_months=1, step_months=1)
    # Only 3 months of data -- not enough for one window
    windows = generate_windows(date(2026, 1, 1), date(2026, 4, 1), config)
    assert len(windows) == 0
