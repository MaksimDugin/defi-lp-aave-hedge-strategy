from __future__ import annotations

import math

import pandas as pd

from strategy.baselines import BuyHoldBaseline, FixedHedgeLPBaseline, PlainLPBaseline
from strategy.config import StrategyConfig


REQUIRED_BASELINE_COLUMNS = {
    "timestamp",
    "strategy_name",
    "eth_price_usdc",
    "nav",
    "regime",
}


def test_buy_hold_baseline_has_required_columns(toy_market_data: pd.DataFrame) -> None:
    result = BuyHoldBaseline(StrategyConfig()).run(toy_market_data)
    assert REQUIRED_BASELINE_COLUMNS.issubset(result.columns)


def test_buy_hold_initial_nav_equals_initial_capital(toy_market_data: pd.DataFrame) -> None:
    config = StrategyConfig(initial_capital_usdc=100_000.0)
    result = BuyHoldBaseline(config).run(toy_market_data)
    assert math.isclose(result["nav"].iloc[0], 100_000.0, rel_tol=1e-9)


def test_buy_hold_nav_formula(toy_market_data: pd.DataFrame) -> None:
    config = StrategyConfig(initial_capital_usdc=100_000.0)
    first_price = toy_market_data["eth_price_usdc"].iloc[0]
    eth_amount = (config.initial_capital_usdc * 0.5) / first_price
    usdc_amount = config.initial_capital_usdc * 0.5

    result = BuyHoldBaseline(config).run(toy_market_data)
    expected_last_nav = eth_amount * toy_market_data["eth_price_usdc"].iloc[-1] + usdc_amount

    assert math.isclose(result["nav"].iloc[-1], expected_last_nav, rel_tol=1e-9)


def test_plain_lp_baseline_has_no_aave_debt(toy_market_data: pd.DataFrame) -> None:
    result = PlainLPBaseline(StrategyConfig()).run(toy_market_data)

    assert "borrowed_weth" in result.columns
    assert "aave_debt_value" in result.columns
    assert (result["borrowed_weth"] == 0).all()
    assert (result["aave_debt_value"] == 0).all()


def test_plain_lp_baseline_records_lp_fees(toy_market_data: pd.DataFrame) -> None:
    result = PlainLPBaseline(StrategyConfig()).run(toy_market_data)

    assert "lp_fees" in result.columns
    assert (result["lp_fees"] >= 0).all()
    assert result["lp_fees"].sum() > 0


def test_fixed_hedge_opens_debt_once_and_keeps_it_constant(toy_market_data: pd.DataFrame) -> None:
    result = FixedHedgeLPBaseline(StrategyConfig()).run(toy_market_data)

    assert "borrowed_weth" in result.columns
    debt = result["borrowed_weth"]

    assert debt.iloc[0] > 0
    assert debt.nunique() == 1


def test_fixed_hedge_has_aave_debt_value(toy_market_data: pd.DataFrame) -> None:
    result = FixedHedgeLPBaseline(StrategyConfig()).run(toy_market_data)

    assert "aave_debt_value" in result.columns
    assert (result["aave_debt_value"] >= 0).all()
    assert result["aave_debt_value"].iloc[0] > 0


def test_all_baselines_return_same_number_of_rows(toy_market_data: pd.DataFrame) -> None:
    config = StrategyConfig()
    buy_hold = BuyHoldBaseline(config).run(toy_market_data)
    plain_lp = PlainLPBaseline(config).run(toy_market_data)
    fixed_hedge = FixedHedgeLPBaseline(config).run(toy_market_data)

    assert len(buy_hold) == len(toy_market_data)
    assert len(plain_lp) == len(toy_market_data)
    assert len(fixed_hedge) == len(toy_market_data)
