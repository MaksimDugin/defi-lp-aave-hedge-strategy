from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import List

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
from strategy.metrics import add_drawdown_column, summarize_strategy


try:
    from fractal.core.base import (
        Action,
        ActionToTake,
        BaseStrategy,
        BaseStrategyParams,
        NamedEntity,
        Observation,
    )
    from fractal.core.entities import (
        UniswapV2LPConfig,
        UniswapV2LPEntity,
        UniswapV2LPGlobalState,
    )
except ImportError as exc:
    raise ImportError(
        "fractal-defi is required for strategy/fractal_runner.py. "
        "Install it with: pip install fractal-defi==1.3.1"
    ) from exc


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "processed" / "market_data.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "results_tables"


@dataclass
class FractalV2HoldParams(BaseStrategyParams):
    INITIAL_BALANCE: float = 100_000.0
    POOL_FEE_RATE: float = 0.003


class FractalV2HoldStrategy(BaseStrategy[FractalV2HoldParams]):
    """
    Deposit once into Uniswap V2 LP and hold.

    This is the actual fractal-defi part:
    - BaseStrategy
    - Observation
    - Action / ActionToTake
    - UniswapV2LPEntity
    - UniswapV2LPGlobalState
    """

    def set_up(self) -> None:
        self.register_entity(
            NamedEntity(
                entity_name="POOL",
                entity=UniswapV2LPEntity(
                    config=UniswapV2LPConfig(
                        pool_fee_rate=self._params.POOL_FEE_RATE,
                        notional_side="token0",
                    )
                ),
            )
        )
        self._opened = False

    def predict(self) -> List[ActionToTake]:
        if self._opened:
            return []

        self._opened = True

        return [
            ActionToTake(
                "POOL",
                Action(
                    "deposit",
                    {"amount_in_notional": self._params.INITIAL_BALANCE},
                ),
            ),
            ActionToTake(
                "POOL",
                Action(
                    "open_position",
                    {"amount_in_notional": self._params.INITIAL_BALANCE},
                ),
            ),
        ]


@dataclass
class HedgeState:
    borrowed_weth: float
    aave_collateral_value: float
    idle_usdc: float
    idle_weth: float = 0.0

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


def load_market_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Market data file not found: {path}")

    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    required = {
        "timestamp",
        "eth_price_usdc",
        "uni_tvl_usd",
        "uni_volume_usd",
        "uni_fees_usd",
        "uni_liquidity",
        "aave_weth_borrow_rate",
        "aave_usdc_supply_rate",
        "gas_cost_usdc",
        "regime",
    }

    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"market_data is missing required columns: {sorted(missing)}")

    df = df[
        (df["eth_price_usdc"] > 0)
        & (df["uni_tvl_usd"] > 0)
        & (df["uni_liquidity"] > 0)
    ].copy()

    if df.empty:
        raise ValueError("No valid market observations after filtering")

    df["eth_return"] = df["eth_price_usdc"].pct_change().fillna(0.0)

    return df.reset_index(drop=True)


def build_fractal_observations(market_data: pd.DataFrame) -> List[Observation]:
    observations: List[Observation] = []

    for _, row in market_data.iterrows():
        observations.append(
            Observation(
                timestamp=row["timestamp"].to_pydatetime(),
                states={
                    "POOL": UniswapV2LPGlobalState(
                        price=float(row["eth_price_usdc"]),
                        tvl=float(row["uni_tvl_usd"]),
                        volume=float(row["uni_volume_usd"]),
                        fees=float(row["uni_fees_usd"]),
                        liquidity=float(row["uni_liquidity"]),
                    )
                },
            )
        )

    return observations


def _extract_fractal_lp_timeseries(
    result_df: pd.DataFrame,
    market_data: pd.DataFrame,
    strategy_name: str,
) -> pd.DataFrame:
    """
    Normalize fractal-defi result to project columns.

    Expected important fractal columns:
    - timestamp
    - net_balance
    - optionally POOL_cumulative_position_fees
    """
    out = pd.DataFrame()

    if "timestamp" not in result_df.columns:
        raise ValueError(f"fractal result does not contain timestamp: {result_df.columns.tolist()}")

    if "net_balance" not in result_df.columns:
        raise ValueError(
            "fractal result does not contain net_balance. "
            f"Available columns: {result_df.columns.tolist()}"
        )

    n = min(len(result_df), len(market_data))

    result_df = result_df.iloc[:n].copy()
    market_data = market_data.iloc[:n].copy()

    out["timestamp"] = pd.to_datetime(result_df["timestamp"], utc=True)
    out["strategy_name"] = strategy_name
    out["eth_price_usdc"] = market_data["eth_price_usdc"].astype(float).to_numpy()
    out["lp_value"] = pd.to_numeric(result_df["net_balance"], errors="coerce").fillna(0.0)

    if "POOL_cumulative_position_fees" in result_df.columns:
        cumulative_fees = pd.to_numeric(
            result_df["POOL_cumulative_position_fees"],
            errors="coerce",
        ).fillna(0.0)
        out["lp_fees"] = cumulative_fees.diff().fillna(cumulative_fees)
    else:
        out["lp_fees"] = 0.0

    out["lp_eth_delta"] = out["lp_value"] / (2.0 * out["eth_price_usdc"])
    out["regime"] = market_data["regime"].to_numpy()

    return out


def run_fractal_lp_leg(
    market_data: pd.DataFrame,
    initial_balance_usdc: float,
    strategy_name: str,
    pool_fee_rate: float = 0.003,
) -> pd.DataFrame:
    observations = build_fractal_observations(market_data)

    strategy = FractalV2HoldStrategy(
        params=FractalV2HoldParams(
            INITIAL_BALANCE=initial_balance_usdc,
            POOL_FEE_RATE=pool_fee_rate,
        )
    )

    result = strategy.run(observations)
    raw = result.to_dataframe()

    return _extract_fractal_lp_timeseries(
        result_df=raw,
        market_data=market_data,
        strategy_name=strategy_name,
    )


def run_buy_hold_baseline(
    market_data: pd.DataFrame,
    config: StrategyConfig,
) -> pd.DataFrame:
    first_price = float(market_data["eth_price_usdc"].iloc[0])
    initial_capital = config.initial_capital_usdc

    eth_amount = (initial_capital * 0.5) / first_price
    usdc_amount = initial_capital * 0.5

    out = pd.DataFrame()
    out["timestamp"] = market_data["timestamp"]
    out["strategy_name"] = "buy_hold_50_50"
    out["eth_price_usdc"] = market_data["eth_price_usdc"].astype(float)
    out["nav"] = eth_amount * out["eth_price_usdc"] + usdc_amount
    out["regime"] = market_data["regime"]
    out["turnover"] = 0.0
    out["rebalance_event"] = False
    out["gas_cost"] = 0.0
    out["slippage_cost"] = 0.0
    out["health_factor"] = math.inf
    out["idle_ratio"] = 0.0

    return add_drawdown_column(out)


def run_fractal_plain_lp(
    market_data: pd.DataFrame,
    config: StrategyConfig,
    pool_fee_rate: float = 0.003,
) -> pd.DataFrame:
    lp = run_fractal_lp_leg(
        market_data=market_data,
        initial_balance_usdc=config.initial_capital_usdc,
        strategy_name="fractal_plain_uniswap_v2_lp",
        pool_fee_rate=pool_fee_rate,
    )

    out = lp.copy()
    out["nav"] = out["lp_value"]
    out["borrowed_weth"] = 0.0
    out["aave_debt_value"] = 0.0
    out["turnover"] = 0.0
    out["rebalance_event"] = False
    out["gas_cost"] = 0.0
    out["slippage_cost"] = 0.0
    out["health_factor"] = math.inf
    out["idle_ratio"] = 0.0

    return add_drawdown_column(out)


def _initialize_hedge_state(
    lp_leg: pd.DataFrame,
    config: StrategyConfig,
) -> HedgeState:
    first = lp_leg.iloc[0]

    initial_lp_delta = float(first["lp_eth_delta"])
    first_price = float(first["eth_price_usdc"])

    borrowed_weth = calculate_target_weth_debt(
        lp_eth_delta=initial_lp_delta,
        hedge_ratio=config.hedge_ratio,
    )

    # Borrowed WETH is assumed to be sold immediately into USDC.
    idle_usdc = borrowed_weth * first_price

    return HedgeState(
        borrowed_weth=borrowed_weth,
        aave_collateral_value=config.initial_capital_usdc * config.aave_collateral_allocation,
        idle_usdc=idle_usdc,
        idle_weth=0.0,
    )


def run_fractal_fixed_hedge_lp(
    market_data: pd.DataFrame,
    config: StrategyConfig,
    pool_fee_rate: float = 0.003,
) -> pd.DataFrame:
    lp_capital = config.initial_capital_usdc * config.lp_allocation

    lp_leg = run_fractal_lp_leg(
        market_data=market_data,
        initial_balance_usdc=lp_capital,
        strategy_name="fractal_fixed_hedge_lp",
        pool_fee_rate=pool_fee_rate,
    )

    state = _initialize_hedge_state(lp_leg, config)

    rows: list[dict] = []

    for i, row in lp_leg.iterrows():
        md = market_data.iloc[i]

        eth_price = float(row["eth_price_usdc"])
        borrow_rate = float(md["aave_weth_borrow_rate"])
        supply_rate = float(md["aave_usdc_supply_rate"])

        if i > 0:
            borrow_cost = state.borrowed_weth * eth_price * borrow_rate
            supply_yield = state.aave_collateral_value * supply_rate

            state.cumulative_borrow_cost += borrow_cost
            state.cumulative_supply_yield += supply_yield

            state.aave_collateral_value += supply_yield
            state.idle_usdc -= borrow_cost
        else:
            borrow_cost = 0.0
            supply_yield = 0.0

        debt_value = calculate_debt_value(
            borrowed_weth=state.borrowed_weth,
            eth_price_usdc=eth_price,
        )

        health_factor = calculate_health_factor(
            collateral_value=state.aave_collateral_value,
            debt_value=debt_value,
            liquidation_threshold=config.liquidation_threshold,
        )

        ltv = calculate_ltv(
            debt_value=debt_value,
            collateral_value=state.aave_collateral_value,
        )

        idle_value = calculate_idle_value(
            idle_usdc=state.idle_usdc,
            idle_weth=state.idle_weth,
            eth_price_usdc=eth_price,
        )

        nav = (
            float(row["lp_value"])
            + state.aave_collateral_value
            - debt_value
            + idle_value
        )

        idle_ratio = calculate_idle_ratio(idle_value=idle_value, nav=nav)

        rows.append(
            {
                "timestamp": row["timestamp"],
                "strategy_name": "fractal_fixed_hedge_lp",
                "eth_price_usdc": eth_price,
                "nav": nav,
                "lp_value": float(row["lp_value"]),
                "lp_eth_delta": float(row["lp_eth_delta"]),
                "aave_collateral_value": state.aave_collateral_value,
                "borrowed_weth": state.borrowed_weth,
                "aave_debt_value": debt_value,
                "target_weth_debt": state.borrowed_weth,
                "hedge_error": 0.0,
                "health_factor": health_factor,
                "ltv": ltv,
                "idle_usdc": state.idle_usdc,
                "idle_weth": state.idle_weth,
                "idle_value": idle_value,
                "idle_ratio": idle_ratio,
                "lp_fees": float(row["lp_fees"]),
                "aave_borrow_cost": borrow_cost,
                "aave_supply_yield": supply_yield,
                "gas_cost": 0.0,
                "slippage_cost": 0.0,
                "cumulative_costs": state.cumulative_costs,
                "turnover": 0.0,
                "rebalance_event": False,
                "circuit_breaker_active": False,
                "regime": row["regime"],
            }
        )

    return add_drawdown_column(pd.DataFrame(rows))


def _rebalance_dynamic_hedge(
    state: HedgeState,
    target_weth_debt: float,
    lp_eth_delta: float,
    eth_price: float,
    market_row: pd.Series,
    health_factor_before: float,
    config: StrategyConfig,
) -> tuple[bool, bool, float, float, float]:
    """
    Returns:
        circuit_breaker_active, rebalance_event, gas_cost, slippage_cost, turnover
    """
    debt_value_before = calculate_debt_value(
        borrowed_weth=state.borrowed_weth,
        eth_price_usdc=eth_price,
    )

    ltv_before = calculate_ltv(
        debt_value=debt_value_before,
        collateral_value=state.aave_collateral_value,
    )

    circuit_breaker_active = is_circuit_breaker_active(
        eth_return=float(market_row["eth_return"]),
        uni_tvl_usd=float(market_row["uni_tvl_usd"]),
        health_factor=health_factor_before,
        borrow_rate=float(market_row["aave_weth_borrow_rate"]),
        max_price_jump=config.max_price_jump,
        min_liquidity=config.min_liquidity_usdc,
        min_health_factor=config.min_health_factor,
        max_borrow_rate=config.max_borrow_rate_per_period,
    )

    if not should_rebalance(
        target_weth_debt=target_weth_debt,
        current_weth_debt=state.borrowed_weth,
        lp_eth_delta=lp_eth_delta,
        threshold=config.rebalance_threshold,
    ):
        return circuit_breaker_active, False, 0.0, 0.0, 0.0

    desired_change = target_weth_debt - state.borrowed_weth

    # Circuit breaker blocks debt increases, but allows debt reduction.
    if circuit_breaker_active and desired_change > 0:
        return circuit_breaker_active, False, 0.0, 0.0, 0.0

    gas_cost = float(market_row.get("gas_cost_usdc", config.gas_cost_usdc))
    gas_cost = gas_cost if gas_cost > 0 else config.gas_cost_usdc

    if desired_change > 0:
        add_weth = desired_change
        turnover = add_weth * eth_price

        projected_debt_value = (state.borrowed_weth + add_weth) * eth_price

        projected_ltv = calculate_ltv(
            debt_value=projected_debt_value,
            collateral_value=state.aave_collateral_value,
        )

        projected_hf = calculate_health_factor(
            collateral_value=state.aave_collateral_value,
            debt_value=projected_debt_value,
            liquidation_threshold=config.liquidation_threshold,
        )

        if projected_ltv > config.max_ltv:
            return circuit_breaker_active, False, 0.0, 0.0, 0.0

        if projected_hf < config.min_health_factor:
            return circuit_breaker_active, False, 0.0, 0.0, 0.0

        slippage_cost = turnover * config.slippage_bps / 10_000.0

        state.borrowed_weth += add_weth
        state.idle_usdc += turnover
        state.idle_usdc -= gas_cost + slippage_cost

    else:
        repay_weth = min(abs(desired_change), state.borrowed_weth)
        turnover = repay_weth * eth_price
        slippage_cost = turnover * config.slippage_bps / 10_000.0

        state.borrowed_weth -= repay_weth
        state.idle_usdc -= turnover
        state.idle_usdc -= gas_cost + slippage_cost

    state.cumulative_gas_cost += gas_cost
    state.cumulative_slippage_cost += slippage_cost
    state.cumulative_turnover += turnover

    return circuit_breaker_active, True, gas_cost, slippage_cost, turnover


def run_fractal_dynamic_aave_hedged_lp(
    market_data: pd.DataFrame,
    config: StrategyConfig,
    pool_fee_rate: float = 0.003,
) -> pd.DataFrame:
    lp_capital = config.initial_capital_usdc * config.lp_allocation

    lp_leg = run_fractal_lp_leg(
        market_data=market_data,
        initial_balance_usdc=lp_capital,
        strategy_name="fractal_dynamic_aave_hedged_lp",
        pool_fee_rate=pool_fee_rate,
    )

    state = _initialize_hedge_state(lp_leg, config)
    rows: list[dict] = []

    for i, row in lp_leg.iterrows():
        md = market_data.iloc[i]

        eth_price = float(row["eth_price_usdc"])
        lp_value = float(row["lp_value"])
        lp_eth_delta = float(row["lp_eth_delta"])

        borrow_rate = float(md["aave_weth_borrow_rate"])
        supply_rate = float(md["aave_usdc_supply_rate"])

        if i > 0:
            borrow_cost = state.borrowed_weth * eth_price * borrow_rate
            supply_yield = state.aave_collateral_value * supply_rate

            state.cumulative_borrow_cost += borrow_cost
            state.cumulative_supply_yield += supply_yield

            state.aave_collateral_value += supply_yield
            state.idle_usdc -= borrow_cost
        else:
            borrow_cost = 0.0
            supply_yield = 0.0

        target_weth_debt = calculate_target_weth_debt(
            lp_eth_delta=lp_eth_delta,
            hedge_ratio=config.hedge_ratio,
        )

        debt_value_before = calculate_debt_value(
            borrowed_weth=state.borrowed_weth,
            eth_price_usdc=eth_price,
        )

        health_factor_before = calculate_health_factor(
            collateral_value=state.aave_collateral_value,
            debt_value=debt_value_before,
            liquidation_threshold=config.liquidation_threshold,
        )

        if i == 0:
            circuit_breaker_active = False
            rebalance_event = False
            gas_cost = 0.0
            slippage_cost = 0.0
            turnover = 0.0
        else:
            (
                circuit_breaker_active,
                rebalance_event,
                gas_cost,
                slippage_cost,
                turnover,
            ) = _rebalance_dynamic_hedge(
                state=state,
                target_weth_debt=target_weth_debt,
                lp_eth_delta=lp_eth_delta,
                eth_price=eth_price,
                market_row=md,
                health_factor_before=health_factor_before,
                config=config,
            )

        debt_value = calculate_debt_value(
            borrowed_weth=state.borrowed_weth,
            eth_price_usdc=eth_price,
        )

        health_factor = calculate_health_factor(
            collateral_value=state.aave_collateral_value,
            debt_value=debt_value,
            liquidation_threshold=config.liquidation_threshold,
        )

        ltv = calculate_ltv(
            debt_value=debt_value,
            collateral_value=state.aave_collateral_value,
        )

        hedge_error = calculate_hedge_error(
            target_weth_debt=target_weth_debt,
            current_weth_debt=state.borrowed_weth,
            lp_eth_delta=lp_eth_delta,
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

        idle_ratio = calculate_idle_ratio(idle_value=idle_value, nav=nav)

        rows.append(
            {
                "timestamp": row["timestamp"],
                "strategy_name": "fractal_dynamic_aave_hedged_lp",
                "eth_price_usdc": eth_price,
                "nav": nav,
                "lp_value": lp_value,
                "lp_eth_delta": lp_eth_delta,
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
                "lp_fees": float(row["lp_fees"]),
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

    return add_drawdown_column(pd.DataFrame(rows))


def build_rebalances_table(nav_timeseries: pd.DataFrame) -> pd.DataFrame:
    if "rebalance_event" not in nav_timeseries.columns:
        return pd.DataFrame()

    events = nav_timeseries[nav_timeseries["rebalance_event"] == True].copy()

    keep_cols = [
        "timestamp",
        "strategy_name",
        "eth_price_usdc",
        "borrowed_weth",
        "target_weth_debt",
        "hedge_error",
        "turnover",
        "gas_cost",
        "slippage_cost",
        "health_factor",
        "regime",
    ]

    for col in keep_cols:
        if col not in events.columns:
            events[col] = pd.NA

    return events[keep_cols].reset_index(drop=True)


def build_pnl_decomposition(nav_timeseries: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for strategy_name, group in nav_timeseries.groupby("strategy_name"):
        group = group.sort_values("timestamp")

        rows.append(
            {
                "strategy_name": strategy_name,
                "initial_nav": float(group["nav"].iloc[0]),
                "final_nav": float(group["nav"].iloc[-1]),
                "net_pnl": float(group["nav"].iloc[-1] - group["nav"].iloc[0]),
                "total_lp_fees": (
                    float(group["lp_fees"].sum())
                    if "lp_fees" in group.columns
                    else 0.0
                ),
                "total_aave_borrow_cost": (
                    float(group["aave_borrow_cost"].sum())
                    if "aave_borrow_cost" in group.columns
                    else 0.0
                ),
                "total_aave_supply_yield": (
                    float(group["aave_supply_yield"].sum())
                    if "aave_supply_yield" in group.columns
                    else 0.0
                ),
                "total_gas_cost": (
                    float(group["gas_cost"].sum())
                    if "gas_cost" in group.columns
                    else 0.0
                ),
                "total_slippage_cost": (
                    float(group["slippage_cost"].sum())
                    if "slippage_cost" in group.columns
                    else 0.0
                ),
                "total_turnover": (
                    float(group["turnover"].sum())
                    if "turnover" in group.columns
                    else 0.0
                ),
            }
        )

    return pd.DataFrame(rows)


def run_all_fractal_backtests(
    market_data: pd.DataFrame,
    config: StrategyConfig,
    pool_fee_rate: float = 0.003,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    buy_hold = run_buy_hold_baseline(market_data, config)

    plain_lp = run_fractal_plain_lp(
        market_data=market_data,
        config=config,
        pool_fee_rate=pool_fee_rate,
    )

    fixed_hedge = run_fractal_fixed_hedge_lp(
        market_data=market_data,
        config=config,
        pool_fee_rate=pool_fee_rate,
    )

    dynamic_hedge = run_fractal_dynamic_aave_hedged_lp(
        market_data=market_data,
        config=config,
        pool_fee_rate=pool_fee_rate,
    )

    nav_timeseries = pd.concat(
        [buy_hold, plain_lp, fixed_hedge, dynamic_hedge],
        ignore_index=True,
        sort=False,
    )

    metrics = pd.DataFrame(
        [
            summarize_strategy(group)
            for _, group in nav_timeseries.groupby("strategy_name")
        ]
    )

    rebalances = build_rebalances_table(nav_timeseries)
    pnl_decomposition = build_pnl_decomposition(nav_timeseries)

    return nav_timeseries, metrics, rebalances, pnl_decomposition


def save_outputs(
    nav_timeseries: pd.DataFrame,
    metrics: pd.DataFrame,
    rebalances: pd.DataFrame,
    pnl_decomposition: pd.DataFrame,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    nav_timeseries.to_csv(output_dir / "nav_timeseries.csv", index=False)
    metrics.to_csv(output_dir / "metrics.csv", index=False)
    rebalances.to_csv(output_dir / "rebalances.csv", index=False)
    pnl_decomposition.to_csv(output_dir / "pnl_decomposition.csv", index=False)

    # Explicit fractal-named copies for transparency.
    nav_timeseries.to_csv(output_dir / "fractal_nav_timeseries.csv", index=False)
    metrics.to_csv(output_dir / "fractal_metrics.csv", index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--data-path",
        default=str(DEFAULT_DATA_PATH),
        help="Path to data/processed/market_data.csv",
    )

    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for backtest outputs",
    )

    parser.add_argument("--initial-capital-usdc", type=float, default=100_000.0)
    parser.add_argument("--hedge-ratio", type=float, default=0.75)
    parser.add_argument("--rebalance-threshold", type=float, default=0.10)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--gas-cost-usdc", type=float, default=15.0)
    parser.add_argument("--pool-fee-rate", type=float, default=0.003)

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    config = StrategyConfig(
        initial_capital_usdc=args.initial_capital_usdc,
        hedge_ratio=args.hedge_ratio,
        rebalance_threshold=args.rebalance_threshold,
        slippage_bps=args.slippage_bps,
        gas_cost_usdc=args.gas_cost_usdc,
    )

    market_data = load_market_data(Path(args.data_path))

    nav_timeseries, metrics, rebalances, pnl_decomposition = run_all_fractal_backtests(
        market_data=market_data,
        config=config,
        pool_fee_rate=args.pool_fee_rate,
    )

    save_outputs(
        nav_timeseries=nav_timeseries,
        metrics=metrics,
        rebalances=rebalances,
        pnl_decomposition=pnl_decomposition,
        output_dir=Path(args.output_dir),
    )

    print(f"Saved fractal-based backtest outputs to {args.output_dir}")
    print("\nMetrics:")
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()