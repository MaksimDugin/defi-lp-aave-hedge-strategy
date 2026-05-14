from __future__ import annotations

import pandas as pd

from strategy.config import StrategyConfig
from strategy.accounting import (
    calculate_debt_value,
    calculate_health_factor,
    calculate_ltv,
    calculate_target_weth_debt,
)


def _prepare_market_data(market_data: pd.DataFrame) -> pd.DataFrame:
    df = market_data.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    if "regime" not in df.columns:
        df["regime"] = "unknown"

    if "gas_cost_usdc" not in df.columns:
        df["gas_cost_usdc"] = 0.0

    return df


def _lp_eth_delta(lp_value: float, eth_price_usdc: float) -> float:
    """
    Approximate Uniswap V2 full-range ETH delta.

    For a 50/50 ETH/USDC LP position:
        ETH inventory ≈ LP value / 2 / ETH price
    """
    if lp_value <= 0 or eth_price_usdc <= 0:
        return 0.0

    return lp_value / (2.0 * eth_price_usdc)

def _initial_lp_units(
    capital_usdc: float,
    initial_tvl_usd: float,
    initial_liquidity: float,
) -> float:
    if initial_tvl_usd <= 0 or initial_liquidity <= 0:
        raise ValueError("Initial TVL and liquidity must be positive")

    initial_share = capital_usdc / initial_tvl_usd
    return initial_share * initial_liquidity


def _current_lp_share(
    lp_units: float,
    current_liquidity: float,
) -> float:
    if current_liquidity <= 0:
        return 0.0

    return lp_units / current_liquidity

class BuyHoldBaseline:
    """
    50/50 ETH/USDC buy-and-hold baseline.
    """

    def __init__(self, config: StrategyConfig):
        self.config = config

    def run(self, market_data: pd.DataFrame) -> pd.DataFrame:
        df = _prepare_market_data(market_data)

        first_price = float(df["eth_price_usdc"].iloc[0])
        initial_capital = self.config.initial_capital_usdc

        eth_amount = (initial_capital * 0.5) / first_price
        usdc_amount = initial_capital * 0.5

        out = pd.DataFrame()
        out["timestamp"] = df["timestamp"]
        out["strategy_name"] = "buy_hold_50_50"
        out["eth_price_usdc"] = df["eth_price_usdc"].astype(float)
        out["nav"] = eth_amount * out["eth_price_usdc"] + usdc_amount
        out["regime"] = df["regime"]

        return out


class PlainLPBaseline:
    """
    Plain Uniswap V2 LP baseline without Aave hedge.
    """

    def __init__(self, config: StrategyConfig):
        self.config = config

    def run(self, market_data: pd.DataFrame) -> pd.DataFrame:
        df = _prepare_market_data(market_data)

        initial_capital = self.config.initial_capital_usdc
        initial_tvl = float(df["uni_tvl_usd"].iloc[0])

        if initial_tvl <= 0:
            raise ValueError("Initial Uniswap TVL must be positive")

        initial_liquidity = float(df["uni_liquidity"].iloc[0])
        lp_units = _initial_lp_units(
            capital_usdc=initial_capital,
            initial_tvl_usd=initial_tvl,
            initial_liquidity=initial_liquidity,
        )

        rows: list[dict] = []
        cumulative_lp_fees = 0.0

        for _, row in df.iterrows():
            eth_price = float(row["eth_price_usdc"])
            pool_tvl = float(row["uni_tvl_usd"])
            pool_fees = float(row["uni_fees_usd"])

            current_liquidity = float(row["uni_liquidity"])
            lp_share = _current_lp_share(lp_units, current_liquidity)

            lp_value = pool_tvl * lp_share
            period_fees = pool_fees * lp_share
            cumulative_lp_fees += period_fees

            nav = lp_value + cumulative_lp_fees

            rows.append(
                {
                    "timestamp": row["timestamp"],
                    "strategy_name": "plain_uniswap_v2_lp",
                    "eth_price_usdc": eth_price,
                    "nav": nav,
                    "lp_value": lp_value,
                    "lp_eth_delta": _lp_eth_delta(lp_value, eth_price),
                    "borrowed_weth": 0.0,
                    "aave_debt_value": 0.0,
                    "lp_fees": period_fees,
                    "cumulative_lp_fees": cumulative_lp_fees,
                    "regime": row["regime"],
                }
            )

        return pd.DataFrame(rows)


class FixedHedgeLPBaseline:
    """
    LP baseline with a fixed initial WETH hedge.

    The initial hedge is opened once and never rebalanced.

    Important:
    - The strategy holds a fixed amount of LP units.
    - Its pool share changes over time as total Uniswap liquidity changes.
    """

    def __init__(self, config: StrategyConfig):
        self.config = config

    def run(self, market_data: pd.DataFrame) -> pd.DataFrame:
        df = _prepare_market_data(market_data)

        initial_capital = self.config.initial_capital_usdc
        lp_capital = initial_capital * self.config.lp_allocation
        collateral_value = initial_capital * self.config.aave_collateral_allocation

        first = df.iloc[0]
        first_price = float(first["eth_price_usdc"])
        initial_tvl = float(first["uni_tvl_usd"])
        initial_liquidity = float(first["uni_liquidity"])

        if initial_tvl <= 0:
            raise ValueError("Initial Uniswap TVL must be positive")

        if initial_liquidity <= 0:
            raise ValueError("Initial Uniswap liquidity must be positive")

        lp_units = _initial_lp_units(
            capital_usdc=lp_capital,
            initial_tvl_usd=initial_tvl,
            initial_liquidity=initial_liquidity,
        )

        initial_lp_share = _current_lp_share(
            lp_units=lp_units,
            current_liquidity=initial_liquidity,
        )

        initial_lp_value = initial_tvl * initial_lp_share
        initial_lp_delta = _lp_eth_delta(initial_lp_value, first_price)

        borrowed_weth = calculate_target_weth_debt(
            lp_eth_delta=initial_lp_delta,
            hedge_ratio=self.config.hedge_ratio,
        )

        # Borrowed WETH is assumed to be sold immediately into USDC.
        idle_usdc = borrowed_weth * first_price

        cumulative_lp_fees = 0.0
        cumulative_borrow_cost = 0.0
        cumulative_supply_yield = 0.0

        rows: list[dict] = []

        for i, row in df.iterrows():
            eth_price = float(row["eth_price_usdc"])
            pool_tvl = float(row["uni_tvl_usd"])
            pool_fees = float(row["uni_fees_usd"])
            current_liquidity = float(row["uni_liquidity"])

            borrow_rate = float(row["aave_weth_borrow_rate"])
            supply_rate = float(row["aave_usdc_supply_rate"])

            lp_share = _current_lp_share(
                lp_units=lp_units,
                current_liquidity=current_liquidity,
            )

            lp_value = pool_tvl * lp_share
            lp_delta = _lp_eth_delta(lp_value, eth_price)

            period_lp_fees = pool_fees * lp_share
            cumulative_lp_fees += period_lp_fees
            idle_usdc += period_lp_fees

            if i > 0:
                borrow_cost = borrowed_weth * eth_price * borrow_rate
                supply_yield = collateral_value * supply_rate

                cumulative_borrow_cost += borrow_cost
                cumulative_supply_yield += supply_yield

                collateral_value += supply_yield
                idle_usdc -= borrow_cost
            else:
                borrow_cost = 0.0
                supply_yield = 0.0

            debt_value = calculate_debt_value(borrowed_weth, eth_price)

            ltv = calculate_ltv(
                debt_value=debt_value,
                collateral_value=collateral_value,
            )

            health_factor = calculate_health_factor(
                collateral_value=collateral_value,
                debt_value=debt_value,
                liquidation_threshold=self.config.liquidation_threshold,
            )

            nav = lp_value + collateral_value - debt_value + idle_usdc

            rows.append(
                {
                    "timestamp": row["timestamp"],
                    "strategy_name": "fixed_hedge_lp",
                    "eth_price_usdc": eth_price,
                    "nav": nav,
                    "lp_value": lp_value,
                    "lp_eth_delta": lp_delta,
                    "aave_collateral_value": collateral_value,
                    "borrowed_weth": borrowed_weth,
                    "aave_debt_value": debt_value,
                    "ltv": ltv,
                    "health_factor": health_factor,
                    "idle_usdc": idle_usdc,
                    "idle_weth": 0.0,
                    "idle_value": idle_usdc,
                    "lp_fees": period_lp_fees,
                    "aave_borrow_cost": borrow_cost,
                    "aave_supply_yield": supply_yield,
                    "cumulative_lp_fees": cumulative_lp_fees,
                    "cumulative_borrow_cost": cumulative_borrow_cost,
                    "cumulative_supply_yield": cumulative_supply_yield,
                    "lp_units": lp_units,
                    "lp_share": lp_share,
                    "regime": row["regime"],
                }
            )

        return pd.DataFrame(rows)