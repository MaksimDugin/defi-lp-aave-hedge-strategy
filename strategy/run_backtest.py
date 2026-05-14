from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from strategy.baselines import BuyHoldBaseline, FixedHedgeLPBaseline, PlainLPBaseline
from strategy.config import StrategyConfig
from strategy.metrics import add_drawdown_column, summarize_strategy
from strategy.strategy import AaveHedgedLPStrategy


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "processed" / "market_data.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "results_tables"


def load_market_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Market data file not found: {path}")

    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.sort_values("timestamp").reset_index(drop=True)


def build_rebalances_table(nav_timeseries: pd.DataFrame) -> pd.DataFrame:
    rows = []

    if "rebalance_event" not in nav_timeseries.columns:
        return pd.DataFrame(
            columns=[
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
        )

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

        row = {
            "strategy_name": strategy_name,
            "initial_nav": float(group["nav"].iloc[0]),
            "final_nav": float(group["nav"].iloc[-1]),
            "net_pnl": float(group["nav"].iloc[-1] - group["nav"].iloc[0]),
            "total_lp_fees": float(group["lp_fees"].sum()) if "lp_fees" in group.columns else 0.0,
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

        rows.append(row)

    return pd.DataFrame(rows)


def run_all_backtests(
    market_data: pd.DataFrame,
    config: StrategyConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    strategies = [
        BuyHoldBaseline(config),
        PlainLPBaseline(config),
        FixedHedgeLPBaseline(config),
        AaveHedgedLPStrategy(config),
    ]

    results = []

    for strategy in strategies:
        result = strategy.run(market_data)
        result = add_drawdown_column(result)
        results.append(result)

    nav_timeseries = pd.concat(results, ignore_index=True, sort=False)

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--data-path",
        default=str(DEFAULT_DATA_PATH),
        help="Path to processed market_data.csv",
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

    nav_timeseries, metrics, rebalances, pnl_decomposition = run_all_backtests(
        market_data=market_data,
        config=config,
    )

    save_outputs(
        nav_timeseries=nav_timeseries,
        metrics=metrics,
        rebalances=rebalances,
        pnl_decomposition=pnl_decomposition,
        output_dir=Path(args.output_dir),
    )

    print(f"Saved nav_timeseries.csv to {args.output_dir}")
    print(f"Saved metrics.csv to {args.output_dir}")
    print(f"Saved rebalances.csv to {args.output_dir}")
    print(f"Saved pnl_decomposition.csv to {args.output_dir}")

    print("\nMetrics:")
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()