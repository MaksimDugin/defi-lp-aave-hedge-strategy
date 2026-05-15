from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy.config import StrategyConfig
from strategy.fractal_runner import run_all_fractal_backtests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "results_tables" / "monte_carlo"
DEFAULT_FIGURES_DIR = PROJECT_ROOT / "reports" / "figures" / "monte_carlo"

PERIODS_PER_YEAR = 365 * 24


@dataclass(frozen=True)
class MonteCarloScenario:
    """
    Synthetic market scenario for stress-testing the LP + Aave hedge strategy.

    drift and volatility are annualized decimal values.
    Example:
        drift = 0.30 means +30% annualized expected drift.
        volatility = 0.80 means 80% annualized volatility.
    """

    name: str
    drift: float
    volatility: float
    n_steps: int = PERIODS_PER_YEAR
    start_price: float = 3_000.0
    start_tvl: float = 30_000_000.0
    base_hourly_volume_usd: float = 100_000.0
    borrow_apy: float = 0.0425
    supply_apy: float = 0.0375
    gas_cost_usdc: float = 15.0

    # Volume model
    volume_vol_sensitivity: float = 12.0
    volume_noise_sigma: float = 0.35

    # TVL model
    tvl_price_beta: float = 0.50
    tvl_noise_sigma: float = 0.01

    # Optional event shock
    shock_step: int | None = None
    shock_return: float = 0.0
    shock_volume_multiplier: float = 1.0


def default_scenarios(n_steps: int = PERIODS_PER_YEAR) -> list[MonteCarloScenario]:
    """
    Scenario set used for the project robustness check.
    """

    return [
        MonteCarloScenario(
            name="sideways_low_vol",
            drift=0.00,
            volatility=0.30,
            n_steps=n_steps,
            base_hourly_volume_usd=80_000.0,
            tvl_noise_sigma=0.03,
        ),
        MonteCarloScenario(
            name="high_vol_chop",
            drift=0.00,
            volatility=0.95,
            n_steps=n_steps,
            base_hourly_volume_usd=160_000.0,
            volume_vol_sensitivity=18.0,
            tvl_noise_sigma=0.05,
        ),
        MonteCarloScenario(
            name="strong_uptrend",
            drift=0.80,
            volatility=0.60,
            n_steps=n_steps,
            base_hourly_volume_usd=140_000.0,
            tvl_noise_sigma=0.04,
        ),
        MonteCarloScenario(
            name="strong_downtrend",
            drift=-0.60,
            volatility=0.70,
            n_steps=n_steps,
            base_hourly_volume_usd=180_000.0,
            volume_vol_sensitivity=18.0,
            tvl_noise_sigma=0.05,
        ),
        MonteCarloScenario(
            name="crash_recovery",
            drift=0.10,
            volatility=0.75,
            n_steps=n_steps,
            base_hourly_volume_usd=160_000.0,
            shock_step=max(24, n_steps // 3),
            shock_return=-0.35,
            shock_volume_multiplier=5.0,
            volume_vol_sensitivity=20.0,
            tvl_noise_sigma=0.06,
        ),
    ]


def generate_synthetic_market_data(
    scenario: MonteCarloScenario,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic hourly market data compatible with strategy.fractal_runner.

    The price process is geometric Brownian motion with an optional one-off
    stress shock. TVL is linked to price and noise. Volume increases with
    absolute returns and random lognormal noise.
    """
    rng = np.random.default_rng(seed)

    dt = 1.0 / PERIODS_PER_YEAR
    mu = scenario.drift
    sigma = scenario.volatility

    log_returns = rng.normal(
        loc=(mu - 0.5 * sigma**2) * dt,
        scale=sigma * math.sqrt(dt),
        size=scenario.n_steps,
    )

    if scenario.shock_step is not None:
        shock_step = min(max(scenario.shock_step, 0), scenario.n_steps - 1)
        log_returns[shock_step] += math.log(max(1.0 + scenario.shock_return, 1e-6))

    log_price = math.log(scenario.start_price) + np.cumsum(log_returns)
    prices = np.exp(log_price)

    timestamps = pd.date_range(
        "2025-01-01",
        periods=scenario.n_steps,
        freq="h",
        tz="UTC",
    )

    simple_returns = pd.Series(prices).pct_change().fillna(0.0).to_numpy()

    # TVL follows price mechanically only partly and also has independent liquidity flow.
    tvl_noise = rng.normal(
        loc=0.0,
        scale=scenario.tvl_noise_sigma,
        size=scenario.n_steps,
    )

    liquidity_flow = np.exp(np.cumsum(tvl_noise))

    tvl = (
        scenario.start_tvl
        * (prices / prices[0]) ** scenario.tvl_price_beta
        * liquidity_flow
    )

    tvl = np.maximum(tvl, 1_000_000.0)

    # Synthetic pool liquidity is not equal to TVL / price.
    # It is a separate state variable. This avoids making LP delta too stable.
    base_liquidity = scenario.start_tvl / scenario.start_price
    liquidity_noise = rng.normal(
        loc=0.0,
        scale=scenario.tvl_noise_sigma * 1.5,
        size=scenario.n_steps,
    )

    uni_liquidity = (
        base_liquidity
        * liquidity_flow
        * np.exp(np.cumsum(liquidity_noise) / 5.0)
    )

    uni_liquidity = np.maximum(uni_liquidity, 1.0)

    volume_noise = rng.lognormal(
        mean=0.0,
        sigma=scenario.volume_noise_sigma,
        size=scenario.n_steps,
    )

    volume = (
        scenario.base_hourly_volume_usd
        * volume_noise
        * (1.0 + scenario.volume_vol_sensitivity * np.abs(simple_returns))
    )

    if scenario.shock_step is not None:
        shock_step = min(max(scenario.shock_step, 0), scenario.n_steps - 1)
        volume[shock_step : min(shock_step + 24, scenario.n_steps)] *= (
            scenario.shock_volume_multiplier
        )

    volume = np.maximum(volume, 1.0)

    borrow_rate = scenario.borrow_apy / PERIODS_PER_YEAR
    supply_rate = scenario.supply_apy / PERIODS_PER_YEAR

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "eth_price_usdc": prices,
            "uni_tvl_usd": tvl,
            "uni_volume_usd": volume,
            "uni_fees_usd": volume * 0.003,
            "uni_liquidity": uni_liquidity,
            "aave_weth_borrow_rate": np.full(scenario.n_steps, borrow_rate),
            "aave_usdc_supply_rate": np.full(scenario.n_steps, supply_rate),
            "gas_cost_usdc": np.full(scenario.n_steps, scenario.gas_cost_usdc),
            "regime": np.full(scenario.n_steps, scenario.name),
        }
    )

    # Derived columns expected by fractal_runner / circuit breaker / EDA-compatible outputs.
    df["eth_return"] = df["eth_price_usdc"].pct_change().fillna(0.0)

    rolling_window = min(168, max(2, scenario.n_steps // 4))
    df["rolling_eth_vol"] = (
        df["eth_return"]
        .rolling(rolling_window)
        .std()
        .fillna(df["eth_return"].expanding().std())
        .fillna(0.0)
        * np.sqrt(PERIODS_PER_YEAR)
    )

    df["volume_tvl_ratio"] = np.where(
        df["uni_tvl_usd"] > 0,
        df["uni_volume_usd"] / df["uni_tvl_usd"],
        0.0,
    )

    df["aave_weth_borrow_apy"] = df["aave_weth_borrow_rate"] * PERIODS_PER_YEAR
    df["aave_usdc_supply_apy"] = df["aave_usdc_supply_rate"] * PERIODS_PER_YEAR
    df["net_funding_spread_apy"] = (
        df["aave_weth_borrow_apy"] - df["aave_usdc_supply_apy"]
    )

    return df


def build_config_from_args(args: argparse.Namespace) -> StrategyConfig:
    """
    Default config uses calibrated parameters from the historical Optuna run.
    """

    return StrategyConfig(
        initial_capital_usdc=args.initial_capital_usdc,
        hedge_ratio=args.hedge_ratio,
        rebalance_threshold=args.rebalance_threshold,
        slippage_bps=args.slippage_bps,
        gas_cost_usdc=args.gas_cost_usdc,
        max_ltv=args.max_ltv,
        min_health_factor=args.min_health_factor,
        max_price_jump=args.max_price_jump,
        min_liquidity_usdc=args.min_liquidity_usdc,
    )


def run_single_path(
    scenario: MonteCarloScenario,
    path_id: int,
    seed: int,
    config: StrategyConfig,
    pool_fee_rate: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    market_data = generate_synthetic_market_data(
        scenario=scenario,
        seed=seed,
    )

    nav, metrics, rebalances, pnl = run_all_fractal_backtests(
        market_data=market_data,
        config=config,
        pool_fee_rate=pool_fee_rate,
    )

    for frame in [nav, metrics, rebalances, pnl]:
        frame["mc_scenario"] = scenario.name
        frame["mc_path_id"] = path_id
        frame["mc_seed"] = seed

    nav["mc_scenario"] = scenario.name
    nav["mc_path_id"] = path_id
    nav["mc_seed"] = seed

    return nav, metrics, rebalances, pnl


def run_monte_carlo(
    scenarios: list[MonteCarloScenario],
    n_paths: int,
    seed: int,
    config: StrategyConfig,
    pool_fee_rate: float = 0.003,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    all_nav: list[pd.DataFrame] = []
    all_metrics: list[pd.DataFrame] = []
    all_rebalances: list[pd.DataFrame] = []
    all_pnl: list[pd.DataFrame] = []

    path_counter = 0

    for scenario_index, scenario in enumerate(scenarios):
        for path_index in range(n_paths):
            path_seed = seed + scenario_index * 100_000 + path_index
            path_counter += 1

            nav, metrics, rebalances, pnl = run_single_path(
                scenario=scenario,
                path_id=path_index,
                seed=path_seed,
                config=config,
                pool_fee_rate=pool_fee_rate,
            )

            all_nav.append(nav)
            all_metrics.append(metrics)
            all_rebalances.append(rebalances)
            all_pnl.append(pnl)

            print(
                f"Finished MC path {path_counter}/"
                f"{len(scenarios) * n_paths}: "
                f"{scenario.name}, path={path_index}, seed={path_seed}"
            )

    nav_df = pd.concat(all_nav, ignore_index=True)
    metrics_df = pd.concat(all_metrics, ignore_index=True)
    rebalances_df = pd.concat(all_rebalances, ignore_index=True)
    pnl_df = pd.concat(all_pnl, ignore_index=True)

    return nav_df, metrics_df, rebalances_df, pnl_df


def summarize_monte_carlo(metrics: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate Monte Carlo metrics by scenario and strategy.
    """
    summary_rows: list[dict[str, Any]] = []

    group_cols = ["mc_scenario", "strategy_name"]

    numeric_cols = [
        "final_nav",
        "net_pnl",
        "annualized_return",
        "annualized_volatility",
        "sharpe",
        "max_drawdown",
        "turnover",
        "number_of_rebalances",
        "total_costs",
        "average_health_factor",
        "average_idle_ratio",
        "mc_max_hedge_error",
        "mc_lp_delta_change",
    ]

    for (scenario, strategy), group in metrics.groupby(group_cols):
        row: dict[str, Any] = {
            "mc_scenario": scenario,
            "strategy_name": strategy,
            "n_paths": len(group),
        }

        for col in numeric_cols:
            if col not in group.columns:
                continue

            s = pd.to_numeric(group[col], errors="coerce").replace(
                [np.inf, -np.inf],
                np.nan,
            )

            row[f"{col}_mean"] = float(s.mean()) if s.notna().any() else np.nan
            row[f"{col}_median"] = float(s.median()) if s.notna().any() else np.nan
            row[f"{col}_p05"] = float(s.quantile(0.05)) if s.notna().any() else np.nan
            row[f"{col}_p95"] = float(s.quantile(0.95)) if s.notna().any() else np.nan

        summary_rows.append(row)

    return pd.DataFrame(summary_rows)


def build_strategy_comparison(metrics: pd.DataFrame) -> pd.DataFrame:
    """
    Compare dynamic hedge against plain LP and fixed hedge path-by-path.
    """
    key_cols = ["mc_scenario", "mc_path_id", "mc_seed"]

    pivot = metrics.pivot_table(
        index=key_cols,
        columns="strategy_name",
        values=["final_nav", "max_drawdown", "sharpe"],
        aggfunc="first",
    )

    pivot.columns = [f"{metric}__{strategy}" for metric, strategy in pivot.columns]
    pivot = pivot.reset_index()

    dynamic = "fractal_dynamic_aave_hedged_lp"
    plain = "fractal_plain_uniswap_v2_lp"
    fixed = "fractal_fixed_hedge_lp"

    out = pivot.copy()

    if f"final_nav__{dynamic}" in out.columns and f"final_nav__{plain}" in out.columns:
        out["dynamic_minus_plain_final_nav"] = (
            out[f"final_nav__{dynamic}"] - out[f"final_nav__{plain}"]
        )

    if f"final_nav__{dynamic}" in out.columns and f"final_nav__{fixed}" in out.columns:
        out["dynamic_minus_fixed_final_nav"] = (
            out[f"final_nav__{dynamic}"] - out[f"final_nav__{fixed}"]
        )

    if f"max_drawdown__{dynamic}" in out.columns and f"max_drawdown__{plain}" in out.columns:
        # Positive value means dynamic has less negative drawdown.
        out["dynamic_drawdown_improvement_vs_plain"] = (
            out[f"max_drawdown__{dynamic}"] - out[f"max_drawdown__{plain}"]
        )

    if f"sharpe__{dynamic}" in out.columns and f"sharpe__{plain}" in out.columns:
        out["dynamic_minus_plain_sharpe"] = (
            out[f"sharpe__{dynamic}"] - out[f"sharpe__{plain}"]
        )

    return out


def summarize_strategy_comparison(comparison: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for scenario, group in comparison.groupby("mc_scenario"):
        row: dict[str, Any] = {
            "mc_scenario": scenario,
            "n_paths": len(group),
        }

        for col in [
            "dynamic_minus_plain_final_nav",
            "dynamic_minus_fixed_final_nav",
            "dynamic_drawdown_improvement_vs_plain",
            "dynamic_minus_plain_sharpe",
        ]:
            if col not in group.columns:
                continue

            s = pd.to_numeric(group[col], errors="coerce").dropna()

            row[f"{col}_mean"] = float(s.mean()) if len(s) else np.nan
            row[f"{col}_median"] = float(s.median()) if len(s) else np.nan

            if col.startswith("dynamic_drawdown_improvement"):
                row[f"{col}_positive_share"] = float((s > 0).mean()) if len(s) else np.nan
            else:
                row[f"{col}_positive_share"] = float((s > 0).mean()) if len(s) else np.nan

        rows.append(row)

    return pd.DataFrame(rows)


def save_monte_carlo_outputs(
    nav: pd.DataFrame,
    metrics: pd.DataFrame,
    rebalances: pd.DataFrame,
    pnl: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = summarize_monte_carlo(metrics)
    comparison = build_strategy_comparison(metrics)
    comparison_summary = summarize_strategy_comparison(comparison)

    paths = {
        "nav_timeseries": output_dir / "monte_carlo_nav_timeseries.csv",
        "metrics": output_dir / "monte_carlo_metrics.csv",
        "rebalances": output_dir / "monte_carlo_rebalances.csv",
        "pnl_decomposition": output_dir / "monte_carlo_pnl_decomposition.csv",
        "summary": output_dir / "monte_carlo_summary.csv",
        "strategy_comparison": output_dir / "monte_carlo_strategy_comparison.csv",
        "strategy_comparison_summary": output_dir
        / "monte_carlo_strategy_comparison_summary.csv",
    }

    nav.to_csv(paths["nav_timeseries"], index=False)
    metrics.to_csv(paths["metrics"], index=False)
    rebalances.to_csv(paths["rebalances"], index=False)
    pnl.to_csv(paths["pnl_decomposition"], index=False)
    summary.to_csv(paths["summary"], index=False)
    comparison.to_csv(paths["strategy_comparison"], index=False)
    comparison_summary.to_csv(paths["strategy_comparison_summary"], index=False)

    return paths


def save_monte_carlo_plots(
    metrics: pd.DataFrame,
    comparison: pd.DataFrame,
    figures_dir: Path,
) -> None:
    """
    Save lightweight plots for whitepaper / presentation.

    Matplotlib defaults are used intentionally.
    """
    import matplotlib.pyplot as plt

    figures_dir.mkdir(parents=True, exist_ok=True)

    dynamic = metrics[metrics["strategy_name"] == "fractal_dynamic_aave_hedged_lp"].copy()

    if not dynamic.empty:
        # Dynamic final NAV distribution by scenario
        scenarios = list(dynamic["mc_scenario"].drop_duplicates())
        data = [
            dynamic.loc[dynamic["mc_scenario"] == s, "final_nav"].astype(float).to_numpy()
            for s in scenarios
        ]

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.boxplot(data, tick_labels=scenarios, showfliers=False)
        ax.set_title("Monte Carlo: Dynamic hedge final NAV by scenario")
        ax.set_ylabel("Final NAV, USDC")
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()
        fig.savefig(figures_dir / "monte_carlo_dynamic_final_nav_boxplot.png")
        plt.close(fig)

        # Dynamic max drawdown distribution by scenario
        data = [
            dynamic.loc[dynamic["mc_scenario"] == s, "max_drawdown"].astype(float).to_numpy()
            * 100.0
            for s in scenarios
        ]

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.boxplot(data, tick_labels=scenarios, showfliers=False)
        ax.set_title("Monte Carlo: Dynamic hedge max drawdown by scenario")
        ax.set_ylabel("Max drawdown, %")
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()
        fig.savefig(figures_dir / "monte_carlo_dynamic_drawdown_boxplot.png")
        plt.close(fig)

    if "dynamic_drawdown_improvement_vs_plain" in comparison.columns:
        scenarios = list(comparison["mc_scenario"].drop_duplicates())
        data = [
            comparison.loc[
                comparison["mc_scenario"] == s,
                "dynamic_drawdown_improvement_vs_plain",
            ]
            .astype(float)
            .to_numpy()
            * 100.0
            for s in scenarios
        ]

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.boxplot(data, tick_labels=scenarios, showfliers=False)
        ax.set_title("Monte Carlo: Drawdown improvement vs plain LP")
        ax.set_ylabel("Max drawdown improvement, percentage points")
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()
        fig.savefig(figures_dir / "monte_carlo_drawdown_improvement_boxplot.png")
        plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for Monte Carlo output tables.",
    )

    parser.add_argument(
        "--figures-dir",
        default=str(DEFAULT_FIGURES_DIR),
        help="Directory for Monte Carlo figures.",
    )

    parser.add_argument("--n-paths", type=int, default=50)
    parser.add_argument("--n-steps", type=int, default=365 * 24)
    parser.add_argument("--seed", type=int, default=42)

    parser.add_argument("--initial-capital-usdc", type=float, default=100_000.0)

    # Defaults are calibrated historical parameters.
    parser.add_argument("--hedge-ratio", type=float, default=0.8499892802109696)
    parser.add_argument("--rebalance-threshold", type=float, default=0.06965934324744885)

    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--gas-cost-usdc", type=float, default=15.0)
    parser.add_argument("--max-ltv", type=float, default=0.50)
    parser.add_argument("--min-health-factor", type=float, default=1.50)
    parser.add_argument("--max-price-jump", type=float, default=0.10)
    parser.add_argument("--min-liquidity-usdc", type=float, default=1_000_000.0)

    parser.add_argument("--pool-fee-rate", type=float, default=0.003)

    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run a quick smoke test with fewer paths and steps.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.quick:
        args.n_paths = min(args.n_paths, 3)
        args.n_steps = min(args.n_steps, 24 * 30)

    config = build_config_from_args(args)

    scenarios = default_scenarios(n_steps=args.n_steps)

    nav, metrics, rebalances, pnl = run_monte_carlo(
        scenarios=scenarios,
        n_paths=args.n_paths,
        seed=args.seed,
        config=config,
        pool_fee_rate=args.pool_fee_rate,
    )

    dynamic = nav[nav["strategy_name"] == "fractal_dynamic_aave_hedged_lp"].copy()

    if "hedge_error" in dynamic.columns:
        max_hedge_error = float(pd.to_numeric(dynamic["hedge_error"], errors="coerce").max())
    else:
        max_hedge_error = np.nan

    if "lp_eth_delta" in dynamic.columns:
        lp_delta_start = float(dynamic["lp_eth_delta"].iloc[0])
        lp_delta_end = float(dynamic["lp_eth_delta"].iloc[-1])
        lp_delta_change = (
            lp_delta_end / lp_delta_start - 1.0
            if lp_delta_start > 0
            else np.nan
        )
    else:
        lp_delta_change = np.nan

    metrics["mc_max_hedge_error"] = np.nan
    metrics["mc_lp_delta_change"] = np.nan

    dynamic_mask = metrics["strategy_name"] == "fractal_dynamic_aave_hedged_lp"
    metrics.loc[dynamic_mask, "mc_max_hedge_error"] = max_hedge_error
    metrics.loc[dynamic_mask, "mc_lp_delta_change"] = lp_delta_change

    output_dir = Path(args.output_dir)
    figures_dir = Path(args.figures_dir)

    paths = save_monte_carlo_outputs(
        nav=nav,
        metrics=metrics,
        rebalances=rebalances,
        pnl=pnl,
        output_dir=output_dir,
    )

    comparison = pd.read_csv(paths["strategy_comparison"])

    save_monte_carlo_plots(
        metrics=metrics,
        comparison=comparison,
        figures_dir=figures_dir,
    )

    summary = pd.read_csv(paths["summary"])
    comparison_summary = pd.read_csv(paths["strategy_comparison_summary"])

    print("\nSaved Monte Carlo outputs:")
    for name, path in paths.items():
        print(f"{name}: {path}")

    print(f"figures_dir: {figures_dir}")

    print("\nMonte Carlo summary:")
    print(summary.to_string(index=False))

    print("\nMonte Carlo strategy comparison summary:")
    print(comparison_summary.to_string(index=False))


if __name__ == "__main__":
    main()