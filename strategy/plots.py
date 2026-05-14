from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_equity_curve(
    nav_timeseries: pd.DataFrame,
    output_path: str | Path,
) -> None:
    df = nav_timeseries.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    fig, ax = plt.subplots(figsize=(12, 6))

    for strategy_name, group in df.groupby("strategy_name"):
        ax.plot(group["timestamp"], group["nav"], label=strategy_name)

    ax.set_title("Strategy NAV over time")
    ax.set_xlabel("Timestamp")
    ax.set_ylabel("NAV, USDC")
    ax.legend()
    ax.grid(True, alpha=0.3)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def plot_drawdown(
    nav_timeseries: pd.DataFrame,
    output_path: str | Path,
) -> None:
    df = nav_timeseries.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    if "drawdown" not in df.columns:
        df["drawdown"] = (
            df.groupby("strategy_name")["nav"]
            .transform(lambda x: x / x.cummax() - 1.0)
        )

    fig, ax = plt.subplots(figsize=(12, 6))

    for strategy_name, group in df.groupby("strategy_name"):
        ax.plot(group["timestamp"], group["drawdown"], label=strategy_name)

    ax.set_title("Strategy drawdown")
    ax.set_xlabel("Timestamp")
    ax.set_ylabel("Drawdown")
    ax.legend()
    ax.grid(True, alpha=0.3)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def plot_hedge_diagnostics(
    nav_timeseries: pd.DataFrame,
    output_path: str | Path,
    strategy_name: str = "dynamic_aave_hedged_lp",
) -> None:
    df = nav_timeseries.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df[df["strategy_name"] == strategy_name].copy()

    required = {"timestamp", "lp_eth_delta", "borrowed_weth", "target_weth_debt"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns for hedge diagnostics: {sorted(missing)}")

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(df["timestamp"], df["lp_eth_delta"], label="LP ETH delta")
    ax.plot(df["timestamp"], df["target_weth_debt"], label="Target WETH debt")
    ax.plot(df["timestamp"], df["borrowed_weth"], label="Borrowed WETH")

    ax.set_title("Hedge diagnostics")
    ax.set_xlabel("Timestamp")
    ax.set_ylabel("WETH")
    ax.legend()
    ax.grid(True, alpha=0.3)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def save_default_plots(
    nav_timeseries_path: str | Path = "reports/results_tables/nav_timeseries.csv",
    figures_dir: str | Path = "reports/figures",
) -> None:
    nav_timeseries_path = Path(nav_timeseries_path)
    figures_dir = Path(figures_dir)

    df = pd.read_csv(nav_timeseries_path, low_memory=False)

    plot_equity_curve(df, figures_dir / "backtest_equity_curve.png")
    plot_drawdown(df, figures_dir / "backtest_drawdown.png")
    plot_hedge_diagnostics(df, figures_dir / "backtest_hedge_diagnostics.png")