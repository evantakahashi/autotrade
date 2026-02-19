# tests/test_metrics.py
import numpy as np
import pandas as pd
from src.research.metrics import compute_metrics

def test_sharpe_positive_for_uptrend():
    # Daily returns with positive drift
    np.random.seed(42)
    returns = pd.Series(np.random.normal(0.001, 0.01, 252))
    metrics = compute_metrics(returns)
    assert metrics["sharpe"] > 0

def test_sharpe_negative_for_downtrend():
    np.random.seed(42)
    returns = pd.Series(np.random.normal(-0.002, 0.01, 252))
    metrics = compute_metrics(returns)
    assert metrics["sharpe"] < 0

def test_cagr_calculation():
    # 10% total return over 252 days ~ 10% CAGR
    returns = pd.Series([0.0] * 251 + [0.10])
    metrics = compute_metrics(returns)
    assert 0.05 < metrics["cagr"] < 0.15

def test_max_drawdown():
    # Goes up 10%, then drops 20% from peak
    prices = [100, 110, 105, 100, 95, 90, 88, 92]
    returns = pd.Series(np.diff(prices) / prices[:-1])
    metrics = compute_metrics(returns)
    assert metrics["max_drawdown"] > 0.15  # ~20% drawdown

def test_hit_rate():
    returns = pd.Series([0.01, -0.005, 0.02, 0.015, -0.01])
    metrics = compute_metrics(returns)
    assert metrics["hit_rate"] == 0.6  # 3 of 5 positive

def test_turnover():
    # positions_changed and total_positions passed as kwargs
    metrics = compute_metrics(
        pd.Series([0.01] * 20),
        positions_changed=4,
        total_positions=10,
        months=1,
    )
    assert metrics["monthly_turnover"] == 0.4  # 4/10

def test_transaction_costs_reduce_returns():
    np.random.seed(42)
    returns = pd.Series(np.random.normal(0.001, 0.01, 252))
    m_no_cost = compute_metrics(returns, transaction_cost_bps=0)
    m_with_cost = compute_metrics(returns, transaction_cost_bps=10,
                                   positions_changed=50, total_positions=10)
    assert m_with_cost["cagr"] <= m_no_cost["cagr"]

def test_all_metrics_present():
    returns = pd.Series(np.random.normal(0.001, 0.01, 100))
    metrics = compute_metrics(returns)
    required = {"sharpe", "cagr", "max_drawdown", "hit_rate", "win_loss_ratio",
                "total_return", "monthly_turnover"}
    assert required.issubset(set(metrics.keys()))
