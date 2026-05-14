from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyConfig:
    """
    Configuration for the Aave-hedged Uniswap V2 LP strategy.

    All rates are decimal values:
    - 0.75 = 75%
    - 0.10 = 10%
    - 10.0 slippage_bps = 10 basis points
    """

    initial_capital_usdc: float = 100_000.0

    # Capital split
    lp_allocation: float = 0.50
    aave_collateral_allocation: float = 0.50

    # Hedge logic
    hedge_ratio: float = 0.75
    rebalance_threshold: float = 0.10

    # Aave risk constraints
    max_ltv: float = 0.50
    liquidation_threshold: float = 0.80
    min_health_factor: float = 1.50
    emergency_health_factor: float = 1.25

    # Execution assumptions
    slippage_bps: float = 10.0
    gas_cost_usdc: float = 15.0

    # Capital efficiency
    idle_ratio_limit: float = 0.05

    # Circuit breaker assumptions
    max_price_jump: float = 0.10
    min_liquidity_usdc: float = 1_000_000.0
    max_borrow_rate_per_period: float = 0.001