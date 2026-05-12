from __future__ import annotations

from datetime import timezone
from pathlib import Path

import pandas as pd
import requests

from research.data_pipeline.config import PipelineConfig, ensure_dirs


def _binance_interval(frequency: str) -> str:
    if frequency == "hourly":
        return "1h"
    if frequency == "daily":
        return "1d"
    raise ValueError(f"Unsupported frequency: {frequency}")


def download_eth_price_coingecko(config: PipelineConfig) -> pd.DataFrame:
    """
    Download ETH/USDC price.

    Function name is kept for compatibility with scripts/download_data.py.
    Implementation uses Binance ETHUSDC klines because it does not require
    an API key and is stable for historical price data.

    If the raw prices file already exists, it will be loaded from disk
    instead of downloading again.
    """
    ensure_dirs()

    # Check if file already exists
    if config.raw_prices_path.exists():
        print(f"Loading existing price data: {config.raw_prices_path}")
        df = pd.read_csv(config.raw_prices_path)
        # Ensure timestamp column is datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        print(f"Loaded {len(df)} rows from existing file")
        return df

    # Otherwise download from Binance
    url = "https://api.binance.com/api/v3/klines"
    interval = _binance_interval(config.frequency)

    start_ms = int(config.start.replace(tzinfo=timezone.utc).timestamp() * 1000)
    end_ms = int(config.end.replace(tzinfo=timezone.utc).timestamp() * 1000)

    rows: list[list] = []
    cursor = start_ms
    limit = 1000

    while cursor < end_ms:
        params = {
            "symbol": "ETHUSDC",
            "interval": interval,
            "startTime": cursor,
            "endTime": end_ms,
            "limit": limit,
        }

        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()

        batch = response.json()
        if not batch:
            break

        rows.extend(batch)

        last_open_time = int(batch[-1][0])
        next_cursor = last_open_time + 1

        if next_cursor <= cursor:
            break

        cursor = next_cursor

        if len(batch) < limit:
            break

    if not rows:
        df = pd.DataFrame(columns=["timestamp", "eth_price_usdc"])
    else:
        df = pd.DataFrame(
            rows,
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_asset_volume",
                "number_of_trades",
                "taker_buy_base_asset_volume",
                "taker_buy_quote_asset_volume",
                "ignore",
            ],
        )

        df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df["eth_price_usdc"] = df["close"].astype(float)

        df = (
            df[["timestamp", "eth_price_usdc"]]
            .drop_duplicates("timestamp")
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

    config.raw_prices_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.raw_prices_path, index=False)

    print(f"Saved ETH/USDC price data: {config.raw_prices_path} ({len(df)} rows)")

    return df