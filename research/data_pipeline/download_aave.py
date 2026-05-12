from __future__ import annotations

import os
from io import StringIO

import pandas as pd
import requests

from research.data_pipeline.config import PipelineConfig, ensure_dirs


FRED_SOFR_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SOFR"
FRED_EFFR_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=EFFR"


def _periods_per_year(frequency: str) -> int:
    if frequency == "hourly":
        return 365 * 24
    if frequency == "daily":
        return 365
    raise ValueError(f"Unsupported frequency: {frequency}")


def _make_output_timeline(config: PipelineConfig) -> pd.DataFrame:
    if config.frequency == "hourly":
        freq = "h"
    elif config.frequency == "daily":
        freq = "D"
    else:
        raise ValueError(f"Unsupported frequency: {config.frequency}")

    return pd.DataFrame(
        {
            "timestamp": pd.date_range(
                start=config.start,
                end=config.end,
                freq=freq,
                tz="UTC",
            )
        }
    )


def _download_fred_series(series: str = "SOFR") -> pd.DataFrame:
    """
    Download a public FRED CSV series without API key.

    Supported:
    - SOFR
    - EFFR

    Output:
    - timestamp
    - annual_rate_decimal
    """
    series = series.upper().strip()

    if series == "SOFR":
        url = FRED_SOFR_CSV_URL
        value_col = "SOFR"
    elif series == "EFFR":
        url = FRED_EFFR_CSV_URL
        value_col = "EFFR"
    else:
        raise ValueError("Only SOFR and EFFR are supported")

    response = requests.get(url, timeout=60)
    response.raise_for_status()

    df = pd.read_csv(StringIO(response.text))

    if "observation_date" not in df.columns:
        raise RuntimeError(f"Unexpected FRED CSV columns: {df.columns.tolist()}")

    if value_col not in df.columns:
        raise RuntimeError(f"FRED CSV does not contain expected column: {value_col}")

    df["timestamp"] = pd.to_datetime(df["observation_date"], utc=True)

    # FRED uses "." for missing values.
    df[value_col] = pd.to_numeric(df[value_col].replace(".", pd.NA), errors="coerce")

    # Percent -> decimal annual rate.
    df["annual_rate_decimal"] = df[value_col] / 100.0

    df = (
        df[["timestamp", "annual_rate_decimal"]]
        .dropna()
        .drop_duplicates("timestamp")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    return df


def _load_macro_funding_proxy(config: PipelineConfig) -> pd.DataFrame:
    """
    Load macro funding proxy from FRED.

    Default: SOFR.
    Fallback option: EFFR.

    Environment:
    - AAVE_RATE_PROXY=SOFR or EFFR
    """
    proxy = os.getenv("AAVE_RATE_PROXY", "SOFR").upper().strip()

    if proxy not in {"SOFR", "EFFR"}:
        raise ValueError("AAVE_RATE_PROXY must be SOFR or EFFR")

    print(f"Downloading FRED {proxy} as Aave funding proxy...")

    rates = _download_fred_series(proxy)

    start = pd.Timestamp(config.start)
    end = pd.Timestamp(config.end)

    rates = rates[
        (rates["timestamp"] >= start)
        & (rates["timestamp"] <= end)
    ].reset_index(drop=True)

    if rates.empty:
        raise RuntimeError(
            f"FRED {proxy} returned no observations for "
            f"{config.start.date()} — {config.end.date()}"
        )

    return rates


def download_aave_v3_rates(config: PipelineConfig) -> pd.DataFrame:
    """
    Build Aave rates from an external macro funding proxy.

    Motivation:
    Historical Aave WETH borrow and USDC supply rates were not reliably
    available from the tested public APIs for the selected period. Therefore,
    we use a reproducible external benchmark: FRED SOFR by default.

    Output rates are per-period decimal rates:
    - aave_weth_borrow_rate
    - aave_usdc_supply_rate

    Default logic:
    - USDC supply APY proxy = SOFR
    - WETH borrow APY proxy = SOFR

    Optional spreads for sensitivity analysis:
    - AAVE_WETH_BORROW_SPREAD_APY
    - AAVE_USDC_SUPPLY_SPREAD_APY
    """
    ensure_dirs()

    if config.raw_aave_path.exists() and config.raw_aave_path.stat().st_size > 0:
        print(f"Loading existing Aave data: {config.raw_aave_path}")
        df = pd.read_csv(config.raw_aave_path, parse_dates=["timestamp"])
        print(f"Loaded {len(df)} rows from existing file")
        return df

    periods = _periods_per_year(config.frequency)

    macro_rates = _load_macro_funding_proxy(config)

    output = _make_output_timeline(config).sort_values("timestamp")

    output = pd.merge_asof(
        output,
        macro_rates.sort_values("timestamp"),
        on="timestamp",
        direction="backward",
    )

    output["annual_rate_decimal"] = (
        output["annual_rate_decimal"]
        .ffill()
        .bfill()
    )

    weth_borrow_spread = float(os.getenv("AAVE_WETH_BORROW_SPREAD_APY", "0.0"))
    usdc_supply_spread = float(os.getenv("AAVE_USDC_SUPPLY_SPREAD_APY", "0.0"))

    output["aave_weth_borrow_apy_proxy"] = (
        output["annual_rate_decimal"] + weth_borrow_spread
    ).clip(lower=0.0)

    output["aave_usdc_supply_apy_proxy"] = (
        output["annual_rate_decimal"] + usdc_supply_spread
    ).clip(lower=0.0)

    output["aave_weth_borrow_rate"] = output["aave_weth_borrow_apy_proxy"] / periods
    output["aave_usdc_supply_rate"] = output["aave_usdc_supply_apy_proxy"] / periods

    df = output[
        [
            "timestamp",
            "aave_weth_borrow_rate",
            "aave_usdc_supply_rate",
        ]
    ].copy()

    config.raw_aave_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.raw_aave_path, index=False)

    proxy = os.getenv("AAVE_RATE_PROXY", "SOFR").upper().strip()

    print(
        f"Saved Aave proxy rates using FRED {proxy}: "
        f"{config.raw_aave_path} ({len(df)} rows)"
    )

    return df