from __future__ import annotations

import pandas as pd

from research.data_pipeline.clean import clean_market_data, merge_on_timestamp, read_csv_timestamp, resample_market_df
from research.data_pipeline.config import PipelineConfig, ensure_dirs
from research.data_pipeline.regimes import add_regime_labels


def build_market_dataset(config: PipelineConfig) -> pd.DataFrame:
    ensure_dirs()

    prices = read_csv_timestamp(str(config.raw_prices_path))
    uniswap = read_csv_timestamp(str(config.raw_uniswap_path))
    aave = read_csv_timestamp(str(config.raw_aave_path))

    prices = resample_market_df(prices, config.frequency)
    uniswap = resample_market_df(uniswap, config.frequency)
    aave = resample_market_df(aave, config.frequency)

    df = merge_on_timestamp([prices, uniswap, aave])
    df["gas_cost_usdc"] = config.gas_cost_usdc
    df = clean_market_data(df)

    # Recalculate Uniswap fees from volume to enforce the exact project assumption.
    df["uni_fees_usd"] = df["uni_volume_usd"] * config.uniswap_v2_fee_rate

    regime_window = 24 if config.frequency == "hourly" else 7
    df = add_regime_labels(df, window=regime_window)

    required = [
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
    df = df[required]
    config.processed_market_data_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.processed_market_data_path, index=False)

    regimes_path = config.processed_market_data_path.parent / "regimes.csv"
    df[["timestamp", "regime"]].to_csv(regimes_path, index=False)
    return df
