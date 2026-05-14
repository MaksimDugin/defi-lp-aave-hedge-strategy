from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

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
from strategy.circuit_breaker import is_circuit_breaker_active
from strategy.config import StrategyConfig


@dataclass
class StrategyState:
    lp_units: float
    borrowed_weth: float
    aave_collateral_value: float
    idle_usdc: float
    idle_weth: float = 0.0

    cumulative_lp_fees: float = 0.0
    cumulative_borrow_cost: float = 0.0
    cumulative_supply_yield: float = 0.0
    cumulative_gas_cost: float = 0.0
    cumulative_slippage_cost: float = 0.0
    cumulative_turnover: float = 0.0

    @property
    def cumulative_costs(self) -> float:
        return (
            self.cumulative_borrow_cost
            + self.cumulative_gas_cost
            + self.cumulative_slippage_cost
        )
    
def _initial_lp_units(
    capital_usdc: float,
    initial_tvl_usd: float,
    initial_liquidity: float,
) -> float:
    if initial_tvl_usd <= 0 or initial_liquidity <= 0:
        raise ValueError("Initial TVL and liquidity must be positive")

    return (capital_usdc / initial_tvl_usd) * initial_liquidity


def _current_lp_share(
    lp_units: float,
    current_liquidity: float,
) -> float:
    if current_liquidity <= 0:
        return 0.0

    return lp_units / current_liquidity


def _prepare_market_data(market_data: pd.DataFrame) -> pd.DataFrame:
    df = market_data.copy()

    required = {
        "timestamp",
        "eth_price_usdc",
        "uni_tvl_usd",
        "uni_fees_usd",
        "aave_weth_borrow_rate",
        "aave_usdc_supply_rate",
    }

    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"market_data is missing required columns: {sorted(missing)}")

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    if "regime" not in df.columns:
        df["regime"] = "unknown"

    if "gas_cost_usdc" not in df.columns:
        df["gas_cost_usdc"] = 0.0

    if "uni_tvl_usd" not in df.columns:
        df["uni_tvl_usd"] = 0.0

    df["eth_return"] = df["eth_price_usdc"].astype(float).pct_change().fillna(0.0)

    return df


def _lp_eth_delta(lp_value: float, eth_price_usdc: float) -> float:
    """
    Approximate ETH inventory / ETH delta of a full-range Uniswap V2 LP.
    """
    if lp_value <= 0 or eth_price_usdc <= 0:
        return 0.0

    return lp_value / (2.0 * eth_price_usdc)


class AaveHedgedLPStrategy:
    """
    Dynamic Uniswap V2 ETH/USDC LP strategy hedged through Aave-style WETH debt.

    Simplified but explicit accounting model:
    - LP value is proportional to pool TVL through lp_share.
    - LP fees are pool-level fees multiplied by lp_share.
    - WETH debt is a short ETH exposure.
    - Borrowed WETH is assumed to be sold into USDC and held as idle cash.
    - Borrow cost, gas and slippage reduce NAV through cumulative costs.
    - Supply yield increases Aave collateral value.
    """

    def __init__(self, config: StrategyConfig):
        self.config = config

    def _initialize_state(self, first_row: pd.Series) -> StrategyState:
        initial_capital = self.config.initial_capital_usdc
        lp_capital = initial_capital * self.config.lp_allocation
        collateral_value = initial_capital * self.config.aave_collateral_allocation

        initial_tvl = float(first_row["uni_tvl_usd"])
        initial_price = float(first_row["eth_price_usdc"])

        if initial_tvl <= 0:
            raise ValueError("Initial Uniswap TVL must be positive")

        initial_liquidity = float(first_row["uni_liquidity"])

        lp_units = _initial_lp_units(
            capital_usdc=lp_capital,
            initial_tvl_usd=initial_tvl,
            initial_liquidity=initial_liquidity,
        )

        lp_share = _current_lp_share(lp_units, initial_liquidity)
        lp_value = initial_tvl * lp_share
        lp_delta = _lp_eth_delta(lp_value, initial_price)

        target_weth_debt = calculate_target_weth_debt(
            lp_eth_delta=lp_delta,
            hedge_ratio=self.config.hedge_ratio,
        )

        # Borrowed WETH is immediately sold to USDC, creating idle USDC.
        idle_usdc = target_weth_debt * initial_price

        return StrategyState(
            lp_units=lp_units,
            borrowed_weth=target_weth_debt,
            aave_collateral_value=collateral_value,
            idle_usdc=idle_usdc,
            idle_weth=0.0,
        )

    def _apply_period_accruals(
        self,
        state: StrategyState,
        row: pd.Series,
        is_initial_row: bool,
    ) -> tuple[float, float, float]:
        eth_price = float(row["eth_price_usdc"])

        lp_share = _current_lp_share(
            lp_units=state.lp_units,
            current_liquidity=float(row["uni_liquidity"]),
        )

        period_lp_fees = float(row["uni_fees_usd"]) * lp_share
        state.cumulative_lp_fees += period_lp_fees
        state.idle_usdc += period_lp_fees

        if is_initial_row:
            return period_lp_fees, 0.0, 0.0

        borrow_cost = (
            state.borrowed_weth
            * eth_price
            * float(row["aave_weth_borrow_rate"])
        )

        supply_yield = (
            state.aave_collateral_value
            * float(row["aave_usdc_supply_rate"])
        )

        state.cumulative_borrow_cost += borrow_cost
        state.cumulative_supply_yield += supply_yield

        state.aave_collateral_value += supply_yield
        state.idle_usdc -= borrow_cost

        return period_lp_fees, borrow_cost, supply_yield

    def _rebalance_if_needed(
        self,
        state: StrategyState,
        row: pd.Series,
        lp_delta: float,
        target_weth_debt: float,
        health_factor: float,
        ltv: float,
        circuit_breaker_active: bool,
    ) -> tuple[bool, float, float, float]:
        """
        Return:
            rebalance_event, gas_cost, slippage_cost, turnover
        """
        eth_price = float(row["eth_price_usdc"])
        gas_cost = float(row.get("gas_cost_usdc", self.config.gas_cost_usdc))
        gas_cost = gas_cost if gas_cost > 0 else self.config.gas_cost_usdc

        rebalance_event = False
        period_gas_cost = 0.0
        period_slippage_cost = 0.0
        period_turnover = 0.0

        if not should_rebalance(
            target_weth_debt=target_weth_debt,
            current_weth_debt=state.borrowed_weth,
            lp_eth_delta=lp_delta,
            threshold=self.config.rebalance_threshold,
        ):
            return rebalance_event, period_gas_cost, period_slippage_cost, period_turnover

        desired_change = target_weth_debt - state.borrowed_weth

        # Circuit breaker blocks debt increases, but allows debt reduction.
        if circuit_breaker_active and desired_change > 0:
            return rebalance_event, period_gas_cost, period_slippage_cost, period_turnover

        if desired_change > 0:
            additional_weth = desired_change
            additional_debt_value = additional_weth * eth_price
            projected_debt_value = (state.borrowed_weth + additional_weth) * eth_price

            projected_ltv = calculate_ltv(
                debt_value=projected_debt_value,
                collateral_value=state.aave_collateral_value,
            )

            projected_hf = calculate_health_factor(
                collateral_value=state.aave_collateral_value,
                debt_value=projected_debt_value,
                liquidation_threshold=self.config.liquidation_threshold,
            )

            if projected_ltv > self.config.max_ltv:
                return rebalance_event, period_gas_cost, period_slippage_cost, period_turnover

            if projected_hf < self.config.min_health_factor:
                return rebalance_event, period_gas_cost, period_slippage_cost, period_turnover

            period_turnover = additional_debt_value
            period_slippage_cost = (
                period_turnover * self.config.slippage_bps / 10_000.0
            )
            period_gas_cost = gas_cost

            state.borrowed_weth += additional_weth
            state.idle_usdc += additional_debt_value
            state.idle_usdc -= period_slippage_cost + period_gas_cost

            rebalance_event = True

        elif desired_change < 0:
            repay_weth = min(abs(desired_change), state.borrowed_weth)
            repay_notional = repay_weth * eth_price

            period_turnover = repay_notional
            period_slippage_cost = (
                period_turnover * self.config.slippage_bps / 10_000.0
            )
            period_gas_cost = gas_cost

            state.borrowed_weth -= repay_weth
            state.idle_usdc -= repay_notional
            state.idle_usdc -= period_slippage_cost + period_gas_cost

            rebalance_event = True

        if rebalance_event:
            state.cumulative_gas_cost += period_gas_cost
            state.cumulative_slippage_cost += period_slippage_cost
            state.cumulative_turnover += period_turnover

        return rebalance_event, period_gas_cost, period_slippage_cost, period_turnover

    def run(self, market_data: pd.DataFrame) -> pd.DataFrame:
        df = _prepare_market_data(market_data)

        if df.empty:
            raise ValueError("market_data is empty")

        state = self._initialize_state(df.iloc[0])
        rows: list[dict] = []

        for i, row in df.iterrows():
            is_initial_row = i == 0
            eth_price = float(row["eth_price_usdc"])

            period_lp_fees, borrow_cost, supply_yield = self._apply_period_accruals(
                state=state,
                row=row,
                is_initial_row=is_initial_row,
            )

            lp_share = _current_lp_share(
                lp_units=state.lp_units,
                current_liquidity=float(row["uni_liquidity"]),
            )

            lp_value = float(row["uni_tvl_usd"]) * lp_share
            lp_delta = _lp_eth_delta(lp_value, eth_price)

            target_weth_debt = calculate_target_weth_debt(
                lp_eth_delta=lp_delta,
                hedge_ratio=self.config.hedge_ratio,
            )

            debt_value_before = calculate_debt_value(
                borrowed_weth=state.borrowed_weth,
                eth_price_usdc=eth_price,
            )

            health_factor_before = calculate_health_factor(
                collateral_value=state.aave_collateral_value,
                debt_value=debt_value_before,
                liquidation_threshold=self.config.liquidation_threshold,
            )

            ltv_before = calculate_ltv(
                debt_value=debt_value_before,
                collateral_value=state.aave_collateral_value,
            )

            circuit_breaker_active = is_circuit_breaker_active(
                eth_return=float(row["eth_return"]),
                uni_tvl_usd=float(row["uni_tvl_usd"]),
                health_factor=health_factor_before,
                borrow_rate=float(row["aave_weth_borrow_rate"]),
                max_price_jump=self.config.max_price_jump,
                min_liquidity=self.config.min_liquidity_usdc,
                min_health_factor=self.config.min_health_factor,
                max_borrow_rate=self.config.max_borrow_rate_per_period,
            )

            if is_initial_row:
                rebalance_event = False
                gas_cost = 0.0
                slippage_cost = 0.0
                turnover = 0.0
            else:
                (
                    rebalance_event,
                    gas_cost,
                    slippage_cost,
                    turnover,
                ) = self._rebalance_if_needed(
                    state=state,
                    row=row,
                    lp_delta=lp_delta,
                    target_weth_debt=target_weth_debt,
                    health_factor=health_factor_before,
                    ltv=ltv_before,
                    circuit_breaker_active=circuit_breaker_active,
                )

            debt_value = calculate_debt_value(
                borrowed_weth=state.borrowed_weth,
                eth_price_usdc=eth_price,
            )

            ltv = calculate_ltv(
                debt_value=debt_value,
                collateral_value=state.aave_collateral_value,
            )

            health_factor = calculate_health_factor(
                collateral_value=state.aave_collateral_value,
                debt_value=debt_value,
                liquidation_threshold=self.config.liquidation_threshold,
            )

            hedge_error = calculate_hedge_error(
                target_weth_debt=target_weth_debt,
                current_weth_debt=state.borrowed_weth,
                lp_eth_delta=lp_delta,
            )

            idle_value = calculate_idle_value(
                idle_usdc=state.idle_usdc,
                idle_weth=state.idle_weth,
                eth_price_usdc=eth_price,
            )

            nav = calculate_nav(
                lp_value=lp_value,
                aave_collateral_value=state.aave_collateral_value,
                aave_debt_value=debt_value,
                idle_value=idle_value,
                cumulative_costs=0.0,
            )

            idle_ratio = calculate_idle_ratio(
                idle_value=idle_value,
                nav=nav,
            )

            rows.append(
                {
                    "timestamp": row["timestamp"],
                    "strategy_name": "dynamic_aave_hedged_lp",
                    "eth_price_usdc": eth_price,
                    "nav": nav,
                    "lp_value": lp_value,
                    "lp_eth_delta": lp_delta,
                    "aave_collateral_value": state.aave_collateral_value,
                    "borrowed_weth": state.borrowed_weth,
                    "aave_debt_value": debt_value,
                    "target_weth_debt": target_weth_debt,
                    "hedge_error": hedge_error,
                    "health_factor": health_factor,
                    "ltv": ltv,
                    "idle_usdc": state.idle_usdc,
                    "idle_weth": state.idle_weth,
                    "idle_value": idle_value,
                    "idle_ratio": idle_ratio,
                    "lp_fees": period_lp_fees,
                    "aave_borrow_cost": borrow_cost,
                    "aave_supply_yield": supply_yield,
                    "gas_cost": gas_cost,
                    "slippage_cost": slippage_cost,
                    "cumulative_costs": state.cumulative_costs,
                    "turnover": turnover,
                    "rebalance_event": rebalance_event,
                    "circuit_breaker_active": circuit_breaker_active,
                    "regime": row["regime"],
                }
            )

        return pd.DataFrame(rows)