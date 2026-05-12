from __future__ import annotations

import math

import pandas as pd

from strategy.metrics import (
    annualized_return,
    annualized_volatility,
    calculate_returns,
    max_drawdown,
    sharpe_ratio,
    summarize_strategy,
)


def test_calculate_returns() -> None:
    nav = pd.Series([100.0, 110.0, 99.0])
    returns = calculate_returns(nav)
    assert math.isclose(returns.iloc[1], 0.10)
    assert math.isclose(returns.iloc[2], -0.10)


def test_max_drawdown() -> None:
    nav = pd.Series([100.0, 120.0, 90.0, 110.0])
    result = max_drawdown(nav)
    assert math.isclose(result, -0.25)


def test_annualized_volatility_positive_for_variable_returns() -> None:
    returns = pd.Series([0.01, -0.02, 0.015, -0.005])
    assert annualized_volatility(returns, periods_per_year=365) > 0


def test_sharpe_ratio_is_finite_for_nonzero_volatility() -> None:
    returns = pd.Series([0.01, -0.02, 0.015, -0.005])
    result = sharpe_ratio(returns, periods_per_year=365)
    assert math.isfinite(result)


def test_annualized_return_positive_when_nav_grows() -> None:
    nav = pd.Series([100.0, 101.0, 102.0, 103.0])
    result = annualized_return(nav, periods_per_year=365)
    assert result > 0


def test_summarize_strategy_returns_required_keys() -> None:
    result = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=4, freq="h", tz="UTC"),
            "strategy_name": "dummy",
            "nav": [100_000.0, 101_000.0, 99_000.0, 102_000.0],
            "turnover": [0.0, 1000.0, 500.0, 0.0],
            "rebalance_event": [False, True, True, False],
            "health_factor": [4.0, 3.8, 3.7, 3.9],
            "idle_ratio": [0.01, 0.02, 0.015, 0.01],
            "gas_cost": [0.0, 15.0, 15.0, 0.0],
            "slippage_cost": [0.0, 5.0, 5.0, 0.0],
        }
    )

    summary = summarize_strategy(result)

    for key in [
        "strategy_name",
        "final_nav",
        "net_pnl",
        "annualized_return",
        "annualized_volatility",
        "sharpe",
        "max_drawdown",
        "turnover",
        "number_of_rebalances",
        "total_costs",
        "average_health_factor",
        "average_idle_ratio",
    ]:
        assert key in summary
