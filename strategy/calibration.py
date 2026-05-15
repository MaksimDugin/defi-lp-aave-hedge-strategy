from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import optuna
import pandas as pd

from strategy.config import StrategyConfig
from strategy.fractal_runner import (
    load_market_data,
    run_all_fractal_backtests,
    save_outputs,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "processed" / "market_data.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "results_tables"
DEFAULT_CALIBRATION_DIR = PROJECT_ROOT / "reports" / "results_tables" / "calibration"
DEFAULT_FIGURES_DIR = PROJECT_ROOT / "reports" / "figures"


TARGET_STRATEGY = "fractal_dynamic_aave_hedged_lp"
PLAIN_LP_BASELINE = "fractal_plain_uniswap_v2_lp"
FIXED_HEDGE_BASELINE = "fractal_fixed_hedge_lp"
BUY_HOLD_BASELINE = "buy_hold_50_50"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default

    if math.isnan(out):
        return default

    return out


def _metric_row(metrics: pd.DataFrame, strategy_name: str) -> pd.Series:
    rows = metrics[metrics["strategy_name"] == strategy_name]

    if rows.empty:
        raise ValueError(
            f"Metrics for strategy '{strategy_name}' not found. "
            f"Available strategies: {metrics['strategy_name'].tolist()}"
        )

    return rows.iloc[0]


def _objective_score(
    target: pd.Series,
    plain_lp: pd.Series,
    initial_capital: float,
    objective_name: str,
    max_drawdown_budget: float,
) -> float:
    """
    Compute scalar calibration objective.

    Supported objectives:
    - sharpe: maximize dynamic strategy Sharpe.
    - final_nav: maximize final NAV.
    - risk_adjusted: maximize Sharpe with drawdown/turnover/cost penalties.
    - relative_sharpe: maximize dynamic Sharpe minus plain LP Sharpe.
    """
    target_sharpe = _safe_float(target.get("sharpe"))
    target_final_nav = _safe_float(target.get("final_nav"))
    target_return = _safe_float(target.get("annualized_return"))
    target_max_drawdown = _safe_float(target.get("max_drawdown"))
    target_turnover = _safe_float(target.get("turnover"))
    target_costs = _safe_float(target.get("total_costs"))
    number_of_rebalances = _safe_float(target.get("number_of_rebalances"))

    plain_sharpe = _safe_float(plain_lp.get("sharpe"))

    drawdown_abs = abs(target_max_drawdown)
    turnover_ratio = target_turnover / initial_capital if initial_capital > 0 else 0.0
    cost_ratio = target_costs / initial_capital if initial_capital > 0 else 0.0

    if objective_name == "sharpe":
        return target_sharpe

    if objective_name == "final_nav":
        return target_final_nav

    if objective_name == "relative_sharpe":
        return target_sharpe - plain_sharpe

    if objective_name == "risk_adjusted":
        rebalance_penalty = 0.0

        if number_of_rebalances == 0:
            rebalance_penalty = 0.15
        drawdown_penalty = max(0.0, drawdown_abs - max_drawdown_budget) * 2.0
        turnover_penalty = turnover_ratio * 0.05
        cost_penalty = cost_ratio * 0.10

        return (
            target_sharpe
            + 0.25 * target_return
            - drawdown_penalty
            - turnover_penalty
            - cost_penalty
            - rebalance_penalty
        )

    raise ValueError(f"Unsupported objective: {objective_name}")


def _trial_to_config(trial: optuna.Trial, initial_capital_usdc: float) -> StrategyConfig:
    """
    Calibrate only strategy-control parameters.

    Fixed from EDA / assumptions / risk policy:
    - gas_cost_usdc
    - slippage_bps
    - max_price_jump
    - min_health_factor
    - max_ltv
    """

    hedge_ratio = trial.suggest_float(
        "hedge_ratio",
        0.20,
        0.85,
    )

    rebalance_threshold = trial.suggest_float(
        "rebalance_threshold",
        0.03,
        0.15,
    )

    return StrategyConfig(
        initial_capital_usdc=initial_capital_usdc,

        # calibrated strategy parameters
        hedge_ratio=hedge_ratio,
        rebalance_threshold=rebalance_threshold,

        # fixed execution assumptions
        slippage_bps=10.0,
        gas_cost_usdc=15.0,

        # fixed EDA/risk-management assumptions
        max_price_jump=0.10,
        min_health_factor=1.50,
        max_ltv=0.50,
    )


def _record_trial_attrs(
    trial: optuna.Trial,
    metrics: pd.DataFrame,
    score: float,
) -> None:
    target = _metric_row(metrics, TARGET_STRATEGY)
    plain_lp = _metric_row(metrics, PLAIN_LP_BASELINE)
    fixed_hedge = _metric_row(metrics, FIXED_HEDGE_BASELINE)
    buy_hold = _metric_row(metrics, BUY_HOLD_BASELINE)

    trial.set_user_attr("score", score)

    for prefix, row in [
        ("target", target),
        ("plain_lp", plain_lp),
        ("fixed_hedge", fixed_hedge),
        ("buy_hold", buy_hold),
    ]:
        for col in [
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
        ]:
            if col in row.index:
                trial.set_user_attr(f"{prefix}_{col}", _safe_float(row[col]))


def objective_factory(
    market_data: pd.DataFrame,
    initial_capital_usdc: float,
    objective_name: str,
    max_drawdown_budget: float,
    pool_fee_rate: float,
):
    def objective(trial: optuna.Trial) -> float:
        config = _trial_to_config(
            trial=trial,
            initial_capital_usdc=initial_capital_usdc,
        )

        _, metrics, _, _ = run_all_fractal_backtests(
            market_data=market_data,
            config=config,
            pool_fee_rate=pool_fee_rate,
        )

        target = _metric_row(metrics, TARGET_STRATEGY)
        plain_lp = _metric_row(metrics, PLAIN_LP_BASELINE)

        score = _objective_score(
            target=target,
            plain_lp=plain_lp,
            initial_capital=initial_capital_usdc,
            objective_name=objective_name,
            max_drawdown_budget=max_drawdown_budget,
        )

        _record_trial_attrs(
            trial=trial,
            metrics=metrics,
            score=score,
        )

        return score

    return objective


def trials_to_dataframe(study: optuna.Study) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for trial in study.trials:
        row: dict[str, Any] = {
            "number": trial.number,
            "state": str(trial.state),
            "value": trial.value,
        }

        for key, value in trial.params.items():
            row[key] = value

        for key, value in trial.user_attrs.items():
            row[key] = value

        rows.append(row)

    return pd.DataFrame(rows)


def save_best_run_outputs(
    market_data: pd.DataFrame,
    best_params: dict[str, Any],
    initial_capital_usdc: float,
    pool_fee_rate: float,
    output_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    config = StrategyConfig(
        initial_capital_usdc=initial_capital_usdc,
        hedge_ratio=float(best_params["hedge_ratio"]),
        rebalance_threshold=float(best_params["rebalance_threshold"]),
        # fixed execution assumptions
        slippage_bps=10.0,
        gas_cost_usdc=15.0,

        # fixed EDA/risk-management parameters
        max_price_jump=0.10,
        min_health_factor=1.50,
        max_ltv=0.50,
    )

    nav_timeseries, metrics, rebalances, pnl_decomposition = run_all_fractal_backtests(
        market_data=market_data,
        config=config,
        pool_fee_rate=pool_fee_rate,
    )

    save_outputs(
        nav_timeseries=nav_timeseries,
        metrics=metrics,
        rebalances=rebalances,
        pnl_decomposition=pnl_decomposition,
        output_dir=output_dir,
    )

    return nav_timeseries, metrics, rebalances, pnl_decomposition


def save_calibration_plots(
    trials_df: pd.DataFrame,
    figures_dir: Path,
) -> None:
    """
    Save simple calibration diagnostics.

    Uses matplotlib defaults intentionally.
    """
    import matplotlib.pyplot as plt

    figures_dir.mkdir(parents=True, exist_ok=True)

    completed = trials_df[
        trials_df["state"].astype(str).str.contains("COMPLETE", na=False)
    ].copy()

    if completed.empty:
        return

    if {"hedge_ratio", "rebalance_threshold", "score"}.issubset(completed.columns):
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.scatter(
            completed["hedge_ratio"],
            completed["rebalance_threshold"],
            s=40,
        )
        ax.set_title("Calibration trials: hedge ratio vs rebalance threshold")
        ax.set_xlabel("hedge_ratio")
        ax.set_ylabel("rebalance_threshold")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(figures_dir / "calibration_trials_scatter.png")
        plt.close(fig)

    if {"hedge_ratio", "rebalance_threshold", "target_sharpe"}.issubset(completed.columns):
        pivot = completed.pivot_table(
            index="rebalance_threshold",
            columns="hedge_ratio",
            values="target_sharpe",
            aggfunc="max",
        )

        if not pivot.empty:
            fig, ax = plt.subplots(figsize=(10, 6))
            image = ax.imshow(pivot.values, aspect="auto", origin="lower")
            ax.set_title("Calibration heatmap: dynamic hedge Sharpe")
            ax.set_xlabel("hedge_ratio")
            ax.set_ylabel("rebalance_threshold")
            ax.set_xticks(range(len(pivot.columns)))
            ax.set_xticklabels([str(x) for x in pivot.columns], rotation=45)
            ax.set_yticks(range(len(pivot.index)))
            ax.set_yticklabels([str(x) for x in pivot.index])
            fig.colorbar(image, ax=ax, label="Sharpe")
            fig.tight_layout()
            fig.savefig(figures_dir / "calibration_heatmap_sharpe.png")
            plt.close(fig)

    if {"hedge_ratio", "rebalance_threshold", "target_max_drawdown"}.issubset(completed.columns):
        pivot = completed.pivot_table(
            index="rebalance_threshold",
            columns="hedge_ratio",
            values="target_max_drawdown",
            aggfunc="max",
        )

        if not pivot.empty:
            fig, ax = plt.subplots(figsize=(10, 6))
            image = ax.imshow(pivot.values, aspect="auto", origin="lower")
            ax.set_title("Calibration heatmap: dynamic hedge max drawdown")
            ax.set_xlabel("hedge_ratio")
            ax.set_ylabel("rebalance_threshold")
            ax.set_xticks(range(len(pivot.columns)))
            ax.set_xticklabels([str(x) for x in pivot.columns], rotation=45)
            ax.set_yticks(range(len(pivot.index)))
            ax.set_yticklabels([str(x) for x in pivot.index])
            fig.colorbar(image, ax=ax, label="Max drawdown")
            fig.tight_layout()
            fig.savefig(figures_dir / "calibration_heatmap_drawdown.png")
            plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--data-path",
        default=str(DEFAULT_DATA_PATH),
        help="Path to data/processed/market_data.csv",
    )

    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_CALIBRATION_DIR),
        help="Directory for calibration outputs",
    )

    parser.add_argument(
        "--figures-dir",
        default=str(DEFAULT_FIGURES_DIR),
        help="Directory for calibration plots",
    )

    parser.add_argument(
        "--best-run-output-dir",
        default=str(DEFAULT_OUTPUT_DIR / "calibrated_best"),
        help="Directory for best-params backtest outputs",
    )

    parser.add_argument("--n-trials", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)

    parser.add_argument(
        "--objective",
        choices=["risk_adjusted", "sharpe", "final_nav", "relative_sharpe"],
        default="risk_adjusted",
    )

    parser.add_argument(
        "--max-drawdown-budget",
        type=float,
        default=0.08,
        help="Drawdown budget used by risk_adjusted objective. Example: 0.08 = 8%",
    )

    parser.add_argument("--initial-capital-usdc", type=float, default=100_000.0)
    parser.add_argument("--pool-fee-rate", type=float, default=0.003)

    parser.add_argument(
        "--storage",
        default=None,
        help="Optional Optuna storage, e.g. sqlite:///reports/results_tables/calibration/optuna.db",
    )

    parser.add_argument(
        "--study-name",
        default="fractal_dynamic_aave_hedged_lp_calibration",
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume existing study with the same study-name and storage.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    data_path = Path(args.data_path)
    output_dir = Path(args.output_dir)
    figures_dir = Path(args.figures_dir)
    best_run_output_dir = Path(args.best_run_output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    market_data = load_market_data(data_path)

    search_space = {
        "hedge_ratio": [0.50, 0.75, 1.00],
        "rebalance_threshold": [0.05, 0.10, 0.15],
    }

    sampler = optuna.samplers.TPESampler(seed=args.seed)

    study = optuna.create_study(
        direction="maximize",
        sampler=sampler,
        study_name=args.study_name,
        storage=args.storage,
        load_if_exists=args.resume,
    )

    objective = objective_factory(
        market_data=market_data,
        initial_capital_usdc=args.initial_capital_usdc,
        objective_name=args.objective,
        max_drawdown_budget=args.max_drawdown_budget,
        pool_fee_rate=args.pool_fee_rate,
    )

    study.optimize(
        objective,
        n_trials=args.n_trials,
        show_progress_bar=True,
    )

    trials_df = trials_to_dataframe(study)
    trials_path = output_dir / "calibration_trials.csv"
    trials_df.to_csv(trials_path, index=False)

    best_params_path = output_dir / "calibration_best_params.json"

    best_payload = {
        "objective": args.objective,
        "best_value": study.best_value,
        "best_params": study.best_params,
        "target_strategy": TARGET_STRATEGY,
        "n_trials": len(study.trials),
        "max_drawdown_budget": args.max_drawdown_budget,
    }

    best_params_path.write_text(
        json.dumps(best_payload, indent=2),
        encoding="utf-8",
    )

    nav_timeseries, metrics, rebalances, pnl_decomposition = save_best_run_outputs(
        market_data=market_data,
        best_params=study.best_params,
        initial_capital_usdc=args.initial_capital_usdc,
        pool_fee_rate=args.pool_fee_rate,
        output_dir=best_run_output_dir,
    )

    metrics.to_csv(output_dir / "calibration_best_metrics.csv", index=False)

    save_calibration_plots(
        trials_df=trials_df,
        figures_dir=figures_dir,
    )

    print(f"Saved calibration trials: {trials_path}")
    print(f"Saved best params: {best_params_path}")
    print(f"Saved best-run outputs: {best_run_output_dir}")

    print("\nBest value:")
    print(study.best_value)

    print("\nBest params:")
    print(json.dumps(study.best_params, indent=2))

    print("\nBest-run metrics:")
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()