from __future__ import annotations

from strategy.circuit_breaker import is_circuit_breaker_active


def test_circuit_breaker_inactive_in_normal_conditions() -> None:
    assert not is_circuit_breaker_active(
        eth_return=0.01,
        uni_tvl_usd=10_000_000.0,
        health_factor=2.0,
        borrow_rate=0.00001,
        max_price_jump=0.10,
        min_liquidity=1_000_000.0,
        min_health_factor=1.5,
        max_borrow_rate=0.001,
    )


def test_circuit_breaker_active_on_large_price_jump() -> None:
    assert is_circuit_breaker_active(
        eth_return=0.25,
        uni_tvl_usd=10_000_000.0,
        health_factor=2.0,
        borrow_rate=0.00001,
        max_price_jump=0.10,
        min_liquidity=1_000_000.0,
        min_health_factor=1.5,
        max_borrow_rate=0.001,
    )


def test_circuit_breaker_active_on_low_liquidity() -> None:
    assert is_circuit_breaker_active(
        eth_return=0.01,
        uni_tvl_usd=100_000.0,
        health_factor=2.0,
        borrow_rate=0.00001,
        max_price_jump=0.10,
        min_liquidity=1_000_000.0,
        min_health_factor=1.5,
        max_borrow_rate=0.001,
    )


def test_circuit_breaker_active_on_low_health_factor() -> None:
    assert is_circuit_breaker_active(
        eth_return=0.01,
        uni_tvl_usd=10_000_000.0,
        health_factor=1.2,
        borrow_rate=0.00001,
        max_price_jump=0.10,
        min_liquidity=1_000_000.0,
        min_health_factor=1.5,
        max_borrow_rate=0.001,
    )


def test_circuit_breaker_active_on_high_borrow_rate() -> None:
    assert is_circuit_breaker_active(
        eth_return=0.01,
        uni_tvl_usd=10_000_000.0,
        health_factor=2.0,
        borrow_rate=0.01,
        max_price_jump=0.10,
        min_liquidity=1_000_000.0,
        min_health_factor=1.5,
        max_borrow_rate=0.001,
    )
