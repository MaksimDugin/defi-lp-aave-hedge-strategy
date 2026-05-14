from __future__ import annotations

import math


def calculate_target_weth_debt(
    lp_eth_delta: float,
    hedge_ratio: float,
) -> float:
    """
    Target WETH debt used as short ETH exposure.

    Formula:
        target_debt = hedge_ratio * LP_ETH_delta
    """
    if lp_eth_delta <= 0 or hedge_ratio <= 0:
        return 0.0

    return lp_eth_delta * hedge_ratio


def calculate_hedge_error(
    target_weth_debt: float,
    current_weth_debt: float,
    lp_eth_delta: float,
) -> float:
    """
    Hedge error normalized by LP ETH delta.

    Formula:
        hedge_error = abs(target_debt - current_debt) / lp_eth_delta

    If lp_eth_delta is zero, there is no meaningful hedge target.
    """
    if lp_eth_delta <= 0:
        return 0.0

    return abs(target_weth_debt - current_weth_debt) / lp_eth_delta


def should_rebalance(
    target_weth_debt: float,
    current_weth_debt: float,
    lp_eth_delta: float,
    threshold: float,
) -> bool:
    """
    Return True if hedge error exceeds rebalance threshold.
    """
    if lp_eth_delta <= 0:
        return False

    hedge_error = calculate_hedge_error(
        target_weth_debt=target_weth_debt,
        current_weth_debt=current_weth_debt,
        lp_eth_delta=lp_eth_delta,
    )

    return hedge_error > threshold


def calculate_idle_value(
    idle_usdc: float,
    idle_weth: float,
    eth_price_usdc: float,
) -> float:
    """
    Value of unused tokens in USDC.
    """
    return idle_usdc + idle_weth * eth_price_usdc


def calculate_idle_ratio(
    idle_value: float,
    nav: float,
) -> float:
    """
    Idle value as a share of NAV.
    """
    if nav <= 0:
        return 0.0

    return idle_value / nav


def calculate_debt_value(
    borrowed_weth: float,
    eth_price_usdc: float,
) -> float:
    """
    WETH debt value in USDC.
    """
    if borrowed_weth <= 0:
        return 0.0

    return borrowed_weth * eth_price_usdc


def calculate_ltv(
    debt_value: float,
    collateral_value: float,
) -> float:
    """
    Loan-to-value ratio.

    Cases:
    - no debt and no collateral -> 0
    - positive debt and no collateral -> infinity
    """
    if debt_value <= 0:
        return 0.0

    if collateral_value <= 0:
        return math.inf

    return debt_value / collateral_value


def calculate_health_factor(
    collateral_value: float,
    debt_value: float,
    liquidation_threshold: float,
) -> float:
    """
    Aave-style health factor.

    Formula:
        HF = collateral_value * liquidation_threshold / debt_value
    """
    if debt_value <= 0:
        return math.inf

    if collateral_value <= 0:
        return 0.0

    return collateral_value * liquidation_threshold / debt_value


def calculate_nav(
    lp_value: float,
    aave_collateral_value: float,
    aave_debt_value: float,
    idle_value: float,
    cumulative_costs: float,
) -> float:
    """
    Full strategy NAV in USDC.

    Formula:
        NAV = LP value + Aave collateral - Aave debt + idle value - costs
    """
    return (
        lp_value
        + aave_collateral_value
        - aave_debt_value
        + idle_value
        - cumulative_costs
    )