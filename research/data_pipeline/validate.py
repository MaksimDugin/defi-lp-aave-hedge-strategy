from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = [
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
]


class DataValidationError(ValueError):
    pass


def validate_market_data(path: str | Path) -> None:
    path = Path(path)
    if not path.exists():
        raise DataValidationError(f"Missing processed data file: {path}")
    df = pd.read_csv(path)

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise DataValidationError(f"Missing columns: {missing}")

    if df.empty:
        raise DataValidationError("market_data.csv is empty")

    timestamps = pd.to_datetime(df["timestamp"], utc=True)
    if not timestamps.is_unique:
        raise DataValidationError("timestamps are not unique")
    if not timestamps.is_monotonic_increasing:
        raise DataValidationError("timestamps are not sorted")

    positive_cols = ["eth_price_usdc", "uni_tvl_usd", "uni_liquidity"]
    for col in positive_cols:
        if not (df[col] > 0).all():
            raise DataValidationError(f"{col} must be positive")

    non_negative_cols = [
        "uni_volume_usd",
        "uni_fees_usd",
        "aave_weth_borrow_rate",
        "aave_usdc_supply_rate",
        "gas_cost_usdc",
    ]
    for col in non_negative_cols:
        if not (df[col] >= 0).all():
            raise DataValidationError(f"{col} must be non-negative")

    expected_fees = df["uni_volume_usd"] * 0.003
    max_abs_error = (df["uni_fees_usd"] - expected_fees).abs().max()
    if max_abs_error > 1e-6:
        raise DataValidationError("uni_fees_usd must equal uni_volume_usd * 0.003")
