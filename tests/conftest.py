from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def toy_market_data() -> pd.DataFrame:
    """Small deterministic dataset used by acceptance tests."""
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2025-01-01 00:00:00+00:00",
                    "2025-01-01 01:00:00+00:00",
                    "2025-01-01 02:00:00+00:00",
                    "2025-01-01 03:00:00+00:00",
                    "2025-01-01 04:00:00+00:00",
                ],
                utc=True,
            ),
            "eth_price_usdc": [2000.0, 2100.0, 1900.0, 2050.0, 2000.0],
            "uni_tvl_usd": [10_000_000.0, 10_100_000.0, 9_900_000.0, 10_050_000.0, 10_020_000.0],
            "uni_volume_usd": [1_000_000.0, 1_200_000.0, 1_500_000.0, 1_300_000.0, 1_100_000.0],
            "uni_fees_usd": [3_000.0, 3_600.0, 4_500.0, 3_900.0, 3_300.0],
            "uni_liquidity": [100_000.0, 100_500.0, 99_500.0, 100_200.0, 100_100.0],
            "aave_weth_borrow_rate": [0.00001, 0.00001, 0.000012, 0.000011, 0.00001],
            "aave_usdc_supply_rate": [0.000002, 0.000002, 0.000002, 0.000002, 0.000002],
            "gas_cost_usdc": [15.0, 15.0, 15.0, 15.0, 15.0],
            "regime": ["start", "uptrend", "downtrend", "chop", "sideways"],
        }
    )


@pytest.fixture
def severe_downtrend_market_data(toy_market_data: pd.DataFrame) -> pd.DataFrame:
    df = toy_market_data.copy()
    df["eth_price_usdc"] = [2000.0, 1700.0, 1400.0, 1200.0, 1000.0]
    df["regime"] = "downtrend"
    return df


@pytest.fixture
def price_spike_market_data(toy_market_data: pd.DataFrame) -> pd.DataFrame:
    df = toy_market_data.copy()
    df["eth_price_usdc"] = [2000.0, 2020.0, 2800.0, 2810.0, 2820.0]
    df["regime"] = "price_spike"
    return df
