from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import requests

from research.data_pipeline.config import PipelineConfig, ensure_dirs


def _normalize_apy(value: float) -> float:
    """Convert APY to decimal if API returns percentages instead of decimals."""
    if value > 1.0:
        return value / 100.0
    return value


def _periods_per_year(frequency: str) -> int:
    return 365 * 24 if frequency == "hourly" else 365


def _window_for(start: datetime, end: datetime) -> str:
    days = (end - start).days + 1
    if days <= 1:
        return "LAST_DAY"
    if days <= 7:
        return "LAST_WEEK"
    if days <= 31:
        return "LAST_MONTH"
    if days <= 183:
        return "LAST_SIX_MONTHS"
    return "LAST_YEAR"


def _post_graphql(endpoint: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(endpoint, json={"query": query, "variables": variables}, timeout=60)
    response.raise_for_status()
    payload = response.json()
    if "errors" in payload:
        raise RuntimeError(f"Aave GraphQL errors: {payload['errors']}")
    return payload.get("data", {})


def _fetch_asset_rates(config: PipelineConfig, asset_address: str) -> pd.DataFrame:
    query = """
    query Rates($req: BorrowAPYHistoryRequest!, $sup: SupplyAPYHistoryRequest!) {
      borrowAPYHistory(request: $req) { date avgRate { value } }
      supplyAPYHistory(request: $sup) { date avgRate { value } }
    }
    """
    window = _window_for(config.start, config.end)
    variables = {
        "req": {
            "market": config.aave_v3_market,
            "underlyingToken": asset_address,
            "window": window,
            "chainId": config.chain_id,
        },
        "sup": {
            "market": config.aave_v3_market,
            "underlyingToken": asset_address,
            "window": window,
            "chainId": config.chain_id,
        },
    }
    data = _post_graphql(config.aave_graphql_endpoint, query, variables)

    def flatten(rows: list[dict[str, Any]], col: str) -> pd.DataFrame:
        if not rows:
            return pd.DataFrame(columns=["timestamp", col])
        out = pd.DataFrame(rows)
        out["timestamp"] = pd.to_datetime(out["date"], utc=True)
        out[col] = out["avgRate"].apply(lambda x: float(x["value"]) if x else 0.0)
        out[col] = out[col].map(_normalize_apy)
        return out[["timestamp", col]]

    borrow = flatten(data.get("borrowAPYHistory") or [], "borrow_apy")
    supply = flatten(data.get("supplyAPYHistory") or [], "supply_apy")
    return supply.merge(borrow, on="timestamp", how="outer").sort_values("timestamp")


def download_aave_v3_rates(config: PipelineConfig) -> pd.DataFrame:
    """Download Aave V3 WETH borrow rates and USDC supply rates.

    Output rates are converted to per-period decimal rates, not annualized APY.
    """
    ensure_dirs()
    weth_rates = _fetch_asset_rates(config, config.weth)
    usdc_rates = _fetch_asset_rates(config, config.usdc)

    periods = _periods_per_year(config.frequency)

    df = pd.DataFrame({"timestamp": pd.date_range(config.start, config.end, freq="h", tz="UTC")})
    if config.frequency == "daily":
        df = pd.DataFrame({"timestamp": pd.date_range(config.start, config.end, freq="D", tz="UTC")})

    if not weth_rates.empty:
        weth_rates = weth_rates.rename(columns={"borrow_apy": "aave_weth_borrow_apy"})[
            ["timestamp", "aave_weth_borrow_apy"]
        ]
        df = pd.merge_asof(
            df.sort_values("timestamp"),
            weth_rates.sort_values("timestamp"),
            on="timestamp",
            direction="backward",
        )
    else:
        df["aave_weth_borrow_apy"] = 0.0

    if not usdc_rates.empty:
        usdc_rates = usdc_rates.rename(columns={"supply_apy": "aave_usdc_supply_apy"})[
            ["timestamp", "aave_usdc_supply_apy"]
        ]
        df = pd.merge_asof(
            df.sort_values("timestamp"),
            usdc_rates.sort_values("timestamp"),
            on="timestamp",
            direction="backward",
        )
    else:
        df["aave_usdc_supply_apy"] = 0.0

    df["aave_weth_borrow_apy"] = df["aave_weth_borrow_apy"].fillna(0.0)
    df["aave_usdc_supply_apy"] = df["aave_usdc_supply_apy"].fillna(0.0)

    df["aave_weth_borrow_rate"] = df["aave_weth_borrow_apy"] / periods
    df["aave_usdc_supply_rate"] = df["aave_usdc_supply_apy"] / periods

    df = df[["timestamp", "aave_weth_borrow_rate", "aave_usdc_supply_rate"]]
    config.raw_aave_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.raw_aave_path, index=False)
    return df
