from __future__ import annotations

import math

import pytest

from strategy.accounting import (
    calculate_debt_value,
    calculate_health_factor,
    calculate_hedge_error,
    calculate_idle_ratio,
    calculate_idle_value,
    calculate_ltv,
    calculate_nav,
    calculate_target_weth_debt,
    should_rebalance,
)


def test_calculate_target_weth_debt() -> None:
    assert calculate_target_weth_debt(lp_eth_delta=10.0, hedge_ratio=0.75) == 7.5


@pytest.mark.parametrize(
    "lp_eth_delta,hedge_ratio",
    [
        (0.0, 0.75),
        (10.0, 0.0),
        (10.0, 0.50),
        (10.0, 0.75),
    ],
)
def test_target_weth_debt_is_non_negative(lp_eth_delta: float, hedge_ratio: float) -> None:
    assert calculate_target_weth_debt(lp_eth_delta, hedge_ratio) >= 0.0


def test_calculate_hedge_error() -> None:
    result = calculate_hedge_error(
        target_weth_debt=7.5,
        current_weth_debt=6.0,
        lp_eth_delta=10.0,
    )
    assert math.isclose(result, 0.15)


def test_hedge_error_is_zero_when_lp_delta_zero() -> None:
    assert calculate_hedge_error(0.0, 0.0, 0.0) == 0.0


def test_should_rebalance_when_error_above_threshold() -> None:
    assert should_rebalance(
        target_weth_debt=7.5,
        current_weth_debt=6.0,
        lp_eth_delta=10.0,
        threshold=0.10,
    )


def test_should_not_rebalance_when_error_below_threshold() -> None:
    assert not should_rebalance(
        target_weth_debt=7.5,
        current_weth_debt=7.0,
        lp_eth_delta=10.0,
        threshold=0.10,
    )


def test_should_not_rebalance_when_lp_delta_zero() -> None:
    assert not should_rebalance(
        target_weth_debt=0.0,
        current_weth_debt=0.0,
        lp_eth_delta=0.0,
        threshold=0.10,
    )


def test_calculate_idle_value() -> None:
    assert calculate_idle_value(idle_usdc=1000.0, idle_weth=0.5, eth_price_usdc=2000.0) == 2000.0


def test_calculate_idle_ratio() -> None:
    assert math.isclose(calculate_idle_ratio(idle_value=2000.0, nav=100_000.0), 0.02)


def test_idle_ratio_is_zero_when_nav_zero() -> None:
    assert calculate_idle_ratio(idle_value=2000.0, nav=0.0) == 0.0


def test_calculate_debt_value() -> None:
    assert calculate_debt_value(borrowed_weth=5.0, eth_price_usdc=2000.0) == 10_000.0


def test_calculate_ltv() -> None:
    assert math.isclose(calculate_ltv(debt_value=10_000.0, collateral_value=50_000.0), 0.20)


def test_ltv_is_infinite_when_debt_positive_and_collateral_zero() -> None:
    assert math.isinf(calculate_ltv(debt_value=10_000.0, collateral_value=0.0))


def test_ltv_is_zero_when_debt_zero_and_collateral_zero() -> None:
    assert calculate_ltv(debt_value=0.0, collateral_value=0.0) == 0.0


def test_calculate_health_factor() -> None:
    result = calculate_health_factor(
        collateral_value=50_000.0,
        debt_value=10_000.0,
        liquidation_threshold=0.80,
    )
    assert math.isclose(result, 4.0)


def test_health_factor_is_infinite_when_debt_zero() -> None:
    assert math.isinf(
        calculate_health_factor(
            collateral_value=50_000.0,
            debt_value=0.0,
            liquidation_threshold=0.80,
        )
    )


def test_calculate_nav_includes_all_components() -> None:
    nav = calculate_nav(
        lp_value=50_000.0,
        aave_collateral_value=50_000.0,
        aave_debt_value=15_000.0,
        idle_value=2_000.0,
        cumulative_costs=100.0,
    )
    assert nav == 86_900.0


def test_nav_decreases_when_debt_increases() -> None:
    low_debt_nav = calculate_nav(50_000.0, 50_000.0, 10_000.0, 0.0, 0.0)
    high_debt_nav = calculate_nav(50_000.0, 50_000.0, 20_000.0, 0.0, 0.0)
    assert high_debt_nav < low_debt_nav


def test_nav_decreases_when_costs_increase() -> None:
    low_cost_nav = calculate_nav(50_000.0, 50_000.0, 10_000.0, 0.0, 100.0)
    high_cost_nav = calculate_nav(50_000.0, 50_000.0, 10_000.0, 0.0, 1000.0)
    assert high_cost_nav < low_cost_nav
