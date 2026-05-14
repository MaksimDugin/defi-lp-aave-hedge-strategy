from __future__ import annotations

import math


def is_circuit_breaker_active(
    eth_return: float,
    uni_tvl_usd: float,
    health_factor: float,
    borrow_rate: float,
    max_price_jump: float,
    min_liquidity: float,
    min_health_factor: float,
    max_borrow_rate: float,
) -> bool:
    """
    Circuit breaker for blocking dangerous debt increases.

    Active if at least one condition is true:
    - ETH price jump is too large;
    - Uniswap pool liquidity is too low;
    - Aave health factor is too low;
    - borrow rate is too high;
    - input is not finite.
    """
    inputs = [
        eth_return,
        uni_tvl_usd,
        health_factor,
        borrow_rate,
        max_price_jump,
        min_liquidity,
        min_health_factor,
        max_borrow_rate,
    ]

    if any(not math.isfinite(float(x)) for x in inputs):
        return True

    if abs(eth_return) > max_price_jump:
        return True

    if uni_tvl_usd < min_liquidity:
        return True

    if health_factor < min_health_factor:
        return True

    if borrow_rate > max_borrow_rate:
        return True

    return False