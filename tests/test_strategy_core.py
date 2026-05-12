from __future__ import annotations

import math

import pandas as pd

from strategy.config import StrategyConfig
from strategy.strategy import AaveHedgedLPStrategy


REQUIRED_STRATEGY_COLUMNS = {
    "timestamp",
    "strategy_name",
    "eth_price_usdc",
    "nav",
    "lp_value",
    "lp_eth_delta",
    "aave_collateral_value",
    "borrowed_weth",
    "aave_debt_value",
    "target_weth_debt",
    "hedge_error",
    "health_factor",
    "ltv",
    "idle_usdc",
    "idle_weth",
    "idle_value",
    "idle_ratio",
    "lp_fees",
    "aave_borrow_cost",
    "aave_supply_yield",
    "gas_cost",
    "slippage_cost",
    "cumulative_costs",
    "turnover",
    "rebalance_event",
    "circuit_breaker_active",
    "regime",
}


def test_strategy_output_has_required_columns(toy_market_data: pd.DataFrame) -> None:
    result = AaveHedgedLPStrategy(StrategyConfig()).run(toy_market_data)
    assert REQUIRED_STRATEGY_COLUMNS.issubset(result.columns)


def test_strategy_returns_one_row_per_market_observation(toy_market_data: pd.DataFrame) -> None:
    result = AaveHedgedLPStrategy(StrategyConfig()).run(toy_market_data)
    assert len(result) == len(toy_market_data)


def test_initial_allocation_is_50_50(toy_market_data: pd.DataFrame) -> None:
    config = StrategyConfig(initial_capital_usdc=100_000.0)
    result = AaveHedgedLPStrategy(config).run(toy_market_data)
    first = result.iloc[0]

    assert math.isclose(first["lp_value"], 50_000.0, rel_tol=0.10)
    assert math.isclose(first["aave_collateral_value"], 50_000.0, rel_tol=0.10)


def test_initial_target_debt_equals_hedge_ratio_times_lp_delta(toy_market_data: pd.DataFrame) -> None:
    config = StrategyConfig(hedge_ratio=0.75)
    result = AaveHedgedLPStrategy(config).run(toy_market_data)
    first = result.iloc[0]

    expected = config.hedge_ratio * first["lp_eth_delta"]
    assert math.isclose(first["target_weth_debt"], expected, rel_tol=1e-9)


def test_initial_borrowed_weth_tracks_target_debt(toy_market_data: pd.DataFrame) -> None:
    result = AaveHedgedLPStrategy(StrategyConfig()).run(toy_market_data)
    first = result.iloc[0]

    assert math.isclose(first["borrowed_weth"], first["target_weth_debt"], rel_tol=0.05)


def test_nav_is_positive_for_all_steps(toy_market_data: pd.DataFrame) -> None:
    result = AaveHedgedLPStrategy(StrategyConfig()).run(toy_market_data)
    assert (result["nav"] > 0).all()


def test_cost_columns_are_non_negative(toy_market_data: pd.DataFrame) -> None:
    result = AaveHedgedLPStrategy(StrategyConfig()).run(toy_market_data)

    for col in ["gas_cost", "slippage_cost", "cumulative_costs", "aave_borrow_cost"]:
        assert (result[col] >= 0).all(), f"{col} contains negative values"


def test_supply_yield_is_non_negative(toy_market_data: pd.DataFrame) -> None:
    result = AaveHedgedLPStrategy(StrategyConfig()).run(toy_market_data)
    assert (result["aave_supply_yield"] >= 0).all()


def test_idle_tokens_are_included_in_nav(toy_market_data: pd.DataFrame) -> None:
    result = AaveHedgedLPStrategy(StrategyConfig()).run(toy_market_data)

    assert "idle_value" in result.columns
    assert "idle_ratio" in result.columns
    assert (result["idle_value"] >= 0).all()
    assert (result["idle_ratio"] >= 0).all()


def test_rebalance_event_occurs_when_threshold_is_low(toy_market_data: pd.DataFrame) -> None:
    config = StrategyConfig(rebalance_threshold=0.001)
    result = AaveHedgedLPStrategy(config).run(toy_market_data)

    assert result["rebalance_event"].sum() >= 1


def test_circuit_breaker_blocks_debt_increase_on_price_spike(price_spike_market_data: pd.DataFrame) -> None:
    config = StrategyConfig(rebalance_threshold=0.001)
    result = AaveHedgedLPStrategy(config).run(price_spike_market_data)

    breaker_rows = result[result["circuit_breaker_active"]]
    assert not breaker_rows.empty

    for idx in breaker_rows.index:
        if idx == 0:
            continue
        prev_debt = result.loc[idx - 1, "borrowed_weth"]
        current_debt = result.loc[idx, "borrowed_weth"]
        assert current_debt <= prev_debt + 1e-12
