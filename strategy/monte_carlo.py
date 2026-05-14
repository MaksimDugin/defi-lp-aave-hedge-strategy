from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from strategy.config import StrategyConfig
from strategy.run_backtest import run_all_backtests


@dataclass(frozen=True)
class MonteCarloScenario:
    name: str
    drift: float
    volatility: float
    n_steps: int = 365 * 24
    start_price: float = 2_000.0
    start_tvl: float = 10_000_000.0
    hourly_volume_usd: float = 1_000_000.0


def generate_synthetic_market_data(
    scenario: MonteCarloScenario,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate simplified hourly market data for stress testing.

    drift and volatility are annualized decimal values.
    """
    rng = np.random.default_rng(seed)

    periods_per_year = 365 * 24

    dt = 1.0 / periods_per_year
    mu = scenario.drift
    sigma = scenario.volatility

    shocks = rng.normal(
        loc=(mu - 0.5 * sigma**2) * dt,
        scale=sigma * np.sqrt(dt),
        size=scenario.n_steps,
    )

    log_price = np.log(scenario.start_price) + np.cumsum(shocks)
    prices = np.exp(log_price)

    timestamps = pd.date_range(
        "2025-01-01",
        periods=scenario.n_steps,
        freq="h",
        tz="UTC",
    )

    returns = pd.Series(prices).pct_change().fillna(0.0).to_numpy()

    tvl = scenario.start_tvl * (prices / prices[0]) ** 0.5
    volume = np.full(scenario.n_steps, scenario.hourly_volume_usd)

    # Higher realized absolute returns imply higher synthetic volume.
    volume = volume * (1.0 + 10.0 * np.abs(returns))

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "eth_price_usdc": prices,
            "uni_tvl_usd": tvl,
            "uni_volume_usd": volume,
            "uni_fees_usd": volume * 0.003,
            "uni_liquidity": tvl / prices,
            "aave_weth_borrow_rate": np.full(scenario.n_steps, 0.04 / periods_per_year),
            "aave_usdc_supply_rate": np.full(scenario.n_steps, 0.03 / periods_per_year),
            "gas_cost_usdc": np.full(scenario.n_steps, 15.0),
            "regime": scenario.name,
        }
    )

    return df


def run_monte_carlo_scenarios(
    config: StrategyConfig | None = None,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if config is None:
        config = StrategyConfig()

    scenarios = [
        MonteCarloScenario(name="strong_uptrend", drift=0.80, volatility=0.60),
        MonteCarloScenario(name="strong_downtrend", drift=-0.60, volatility=0.70),
        MonteCarloScenario(name="sideways_low_vol", drift=0.00, volatility=0.30),
        MonteCarloScenario(name="high_vol_chop", drift=0.00, volatility=1.00),
        MonteCarloScenario(name="crash_recovery", drift=-0.20, volatility=1.20),
    ]

    all_nav = []
    all_metrics = []

    for i, scenario in enumerate(scenarios):
        market_data = generate_synthetic_market_data(
            scenario=scenario,
            seed=seed + i,
        )

        nav, metrics, _, _ = run_all_backtests(
            market_data=market_data,
            config=config,
        )

        nav["mc_scenario"] = scenario.name
        metrics["mc_scenario"] = scenario.name

        all_nav.append(nav)
        all_metrics.append(metrics)

    return (
        pd.concat(all_nav, ignore_index=True),
        pd.concat(all_metrics, ignore_index=True),
    )