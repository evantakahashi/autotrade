# src/research/windows.py
from datetime import date
from dateutil.relativedelta import relativedelta
from src.strategy.config import BacktestConfig

def generate_windows(
    data_start: date,
    data_end: date,
    config: BacktestConfig,
) -> list[dict]:
    """Generate rolling walk-forward windows. Returns list of window dicts."""
    step = relativedelta(months=config.step_months)

    windows = []
    window_id = 0
    cursor = data_start

    while True:
        train_start = cursor
        train_end = train_start + relativedelta(months=config.train_months)
        val_start = train_end
        val_end = val_start + relativedelta(months=config.validation_months)
        test_start = val_end
        test_end = test_start + relativedelta(months=config.test_months)

        if test_end > data_end:
            break

        windows.append({
            "window_id": window_id,
            "train_start": train_start,
            "train_end": train_end,
            "validation_start": val_start,
            "validation_end": val_end,
            "test_start": test_start,
            "test_end": test_end,
        })
        window_id += 1
        cursor += step

    return windows
