from pathlib import Path

import pandas as pd
import pytest

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


def load_market_data() -> pd.DataFrame:
    processed = Path("data/processed/market_data.csv")
    if processed.exists():
        return pd.read_csv(processed)
    return pd.read_csv("research/fixtures/toy_market_data.csv")


def test_market_data_schema():
    df = load_market_data()
    for col in REQUIRED_COLUMNS:
        assert col in df.columns, f"Missing column: {col}"


def test_market_data_no_duplicate_timestamps():
    df = load_market_data()
    assert df["timestamp"].is_unique


def test_market_data_sorted_by_timestamp():
    df = load_market_data()
    timestamps = pd.to_datetime(df["timestamp"], utc=True)
    assert timestamps.is_monotonic_increasing


def test_market_data_positive_prices():
    df = load_market_data()
    assert (df["eth_price_usdc"] > 0).all()


def test_market_data_non_negative_rates():
    df = load_market_data()
    assert (df["aave_weth_borrow_rate"] >= 0).all()
    assert (df["aave_usdc_supply_rate"] >= 0).all()


def test_uniswap_fees_equal_volume_times_fee_rate():
    df = load_market_data()
    expected_fees = df["uni_volume_usd"] * 0.003
    assert ((df["uni_fees_usd"] - expected_fees).abs() < 1e-6).all()
