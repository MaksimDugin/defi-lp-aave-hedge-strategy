from __future__ import annotations

import math
from typing import Any

import pandas as pd


def calculate_returns(nav: pd.Series) -> pd.Series:
    """
    Period returns from NAV series.

    First return is set to 0.0 for convenience.
    """
    returns = nav.astype(float).pct_change()
    return returns.fillna(0.0)


def annualized_return(
    nav: pd.Series,
    periods_per_year: int,
) -> float:
    """
    Compound annualized return based on first and last NAV.
    """
    nav = nav.astype(float).dropna()

    if len(nav) < 2:
        return 0.0

    start_nav = nav.iloc[0]
    end_nav = nav.iloc[-1]

    if start_nav <= 0 or end_nav <= 0:
        return 0.0

    periods = len(nav) - 1

    return (end_nav / start_nav) ** (periods_per_year / periods) - 1.0


def annualized_volatility(
    returns: pd.Series,
    periods_per_year: int,
) -> float:
    """
    Annualized volatility from period returns.
    """
    returns = returns.astype(float).dropna()

    if len(returns) < 2:
        return 0.0

    vol = returns.std(ddof=1)

    if not math.isfinite(vol):
        return 0.0

    return vol * math.sqrt(periods_per_year)


def sharpe_ratio(
    returns: pd.Series,
    periods_per_year: int,
    risk_free_rate: float = 0.0,
) -> float:
    """
    Annualized Sharpe ratio.

    risk_free_rate is annual decimal rate.
    """
    returns = returns.astype(float).dropna()

    if len(returns) < 2:
        return 0.0

    period_rf = risk_free_rate / periods_per_year
    excess = returns - period_rf

    vol = annualized_volatility(excess, periods_per_year)

    if vol == 0 or not math.isfinite(vol):
        return 0.0

    ann_excess_return = excess.mean() * periods_per_year

    return ann_excess_return / vol


def max_drawdown(nav: pd.Series) -> float:
    """
    Maximum drawdown as a negative decimal value.

    Example:
        -0.25 means -25%.
    """
    nav = nav.astype(float).dropna()

    if nav.empty:
        return 0.0

    running_max = nav.cummax()
    drawdown = nav / running_max - 1.0

    return float(drawdown.min())


def add_drawdown_column(result: pd.DataFrame) -> pd.DataFrame:
    """
    Return a copy with drawdown column.
    """
    out = result.copy()

    if "nav" not in out.columns:
        raise ValueError("result must contain 'nav' column")

    running_max = out["nav"].astype(float).cummax()
    out["drawdown"] = out["nav"].astype(float) / running_max - 1.0

    return out


def infer_periods_per_year(result: pd.DataFrame) -> int:
    """
    Infer periods per year from timestamp frequency.

    Defaults to hourly if inference is not possible.
    """
    if "timestamp" not in result.columns or len(result) < 3:
        return 365 * 24

    timestamps = pd.to_datetime(result["timestamp"], utc=True).sort_values()
    diffs = timestamps.diff().dropna()

    if diffs.empty:
        return 365 * 24

    median_seconds = diffs.median().total_seconds()

    if median_seconds <= 0:
        return 365 * 24

    return int(round((365 * 24 * 60 * 60) / median_seconds))


def summarize_strategy(
    result: pd.DataFrame,
    periods_per_year: int | None = None,
) -> dict[str, Any]:
    """
    Strategy-level metrics summary.

    Expected optional columns:
    - turnover
    - rebalance_event
    - gas_cost
    - slippage_cost
    - health_factor
    - idle_ratio
    """
    if result.empty:
        raise ValueError("result is empty")

    if "nav" not in result.columns:
        raise ValueError("result must contain 'nav' column")

    if periods_per_year is None:
        periods_per_year = infer_periods_per_year(result)

    nav = result["nav"].astype(float)
    returns = calculate_returns(nav)

    strategy_name = (
        str(result["strategy_name"].iloc[0])
        if "strategy_name" in result.columns and len(result["strategy_name"]) > 0
        else "unknown"
    )

    final_nav = float(nav.iloc[-1])
    initial_nav = float(nav.iloc[0])
    net_pnl = final_nav - initial_nav

    gas_cost = (
        float(result["gas_cost"].sum())
        if "gas_cost" in result.columns
        else 0.0
    )

    slippage_cost = (
        float(result["slippage_cost"].sum())
        if "slippage_cost" in result.columns
        else 0.0
    )

    total_costs = gas_cost + slippage_cost

    turnover = (
        float(result["turnover"].sum())
        if "turnover" in result.columns
        else 0.0
    )

    number_of_rebalances = (
        int(result["rebalance_event"].sum())
        if "rebalance_event" in result.columns
        else 0
    )

    if "health_factor" in result.columns:
        hf_series = (
            pd.to_numeric(result["health_factor"], errors="coerce")
            .replace([math.inf, -math.inf], pd.NA)
            .dropna()
        )
        average_health_factor = float(hf_series.mean()) if not hf_series.empty else math.inf
    else:
        average_health_factor = math.inf

    if "idle_ratio" in result.columns:
        idle_series = pd.to_numeric(result["idle_ratio"], errors="coerce").dropna()
        average_idle_ratio = float(idle_series.mean()) if not idle_series.empty else 0.0
    else:
        average_idle_ratio = 0.0

    return {
        "strategy_name": strategy_name,
        "final_nav": final_nav,
        "net_pnl": net_pnl,
        "annualized_return": annualized_return(nav, periods_per_year),
        "annualized_volatility": annualized_volatility(returns, periods_per_year),
        "sharpe": sharpe_ratio(returns, periods_per_year),
        "max_drawdown": max_drawdown(nav),
        "turnover": turnover,
        "number_of_rebalances": number_of_rebalances,
        "total_costs": total_costs,
        "average_health_factor": average_health_factor,
        "average_idle_ratio": average_idle_ratio,
    }