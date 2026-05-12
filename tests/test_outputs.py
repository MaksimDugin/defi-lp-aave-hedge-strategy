from __future__ import annotations

from pathlib import Path

import pandas as pd


def test_expected_output_files_exist_after_backtest() -> None:
    """
    This test is intended to be run after strategy/run_backtest.py.
    It is skipped automatically if output directory does not exist yet.
    """
    output_dir = Path("reports/results_tables")
    if not output_dir.exists():
        return

    expected_files = [
        output_dir / "nav_timeseries.csv",
        output_dir / "metrics.csv",
        output_dir / "rebalances.csv",
        output_dir / "pnl_decomposition.csv",
    ]

    for path in expected_files:
        assert path.exists(), f"Missing output file: {path}"


def test_nav_timeseries_schema_after_backtest() -> None:
    path = Path("reports/results_tables/nav_timeseries.csv")
    if not path.exists():
        return

    df = pd.read_csv(path)
    required = {"timestamp", "strategy_name", "nav", "eth_price_usdc", "drawdown", "regime"}
    assert required.issubset(df.columns)
    assert (df["nav"] > 0).all()


def test_metrics_schema_after_backtest() -> None:
    path = Path("reports/results_tables/metrics.csv")
    if not path.exists():
        return

    df = pd.read_csv(path)
    required = {
        "strategy_name",
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
    }
    assert required.issubset(df.columns)
