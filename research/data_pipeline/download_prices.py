from __future__ import annotations

import pandas as pd
import requests

from research.data_pipeline.config import PipelineConfig, ensure_dirs


def download_eth_price_coingecko(config: PipelineConfig) -> pd.DataFrame:
    """Download ETH/USD price from CoinGecko and use it as ETH/USDC proxy."""
    ensure_dirs()
    url = "https://api.coingecko.com/api/v3/coins/ethereum/market_chart/range"
    headers = {}
    if config.coingecko_api_key:
        headers["x-cg-demo-api-key"] = config.coingecko_api_key
    params = {
        "vs_currency": "usd",
        "from": int(config.start.timestamp()),
        "to": int(config.end.timestamp()),
    }
    response = requests.get(url, params=params, headers=headers, timeout=60)
    response.raise_for_status()
    payload = response.json()
    prices = payload.get("prices") or []
    df = pd.DataFrame(prices, columns=["timestamp_ms", "eth_price_usdc"])
    if df.empty:
        df = pd.DataFrame(columns=["timestamp", "eth_price_usdc"])
    else:
        df["timestamp"] = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True)
        df = df[["timestamp", "eth_price_usdc"]]
        rule = "1h" if config.frequency == "hourly" else "1D"
        df = (
            df.set_index("timestamp")
            .sort_index()
            .resample(rule)
            .last()
            .ffill()
            .reset_index()
        )
    config.raw_prices_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.raw_prices_path, index=False)
    return df
