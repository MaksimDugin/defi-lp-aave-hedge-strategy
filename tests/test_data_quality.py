from pathlib import Path

import pandas as pd


def load_market_data() -> pd.DataFrame:
    processed = Path("data/processed/market_data.csv")
    if processed.exists():
        return pd.read_csv(processed)
    return pd.read_csv("research/fixtures/toy_market_data.csv")


def test_uniswap_tvl_positive():
    df = load_market_data()
    assert (df["uni_tvl_usd"] > 0).all()


def test_uniswap_liquidity_positive():
    df = load_market_data()
    assert (df["uni_liquidity"] > 0).all()


def test_volume_and_fees_non_negative():
    df = load_market_data()
    assert (df["uni_volume_usd"] >= 0).all()
    assert (df["uni_fees_usd"] >= 0).all()


def test_regime_column_has_no_nulls():
    df = load_market_data()
    assert df["regime"].notna().all()
