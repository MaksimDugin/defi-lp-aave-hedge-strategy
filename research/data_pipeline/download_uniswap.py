from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import requests

from research.data_pipeline.config import PipelineConfig, ensure_dirs


def _to_unix(dt: datetime) -> int:
    return int(dt.timestamp())


def _post_graphql(endpoint: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.post(
        endpoint,
        json={"query": query, "variables": variables or {}},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if "errors" in payload:
        raise RuntimeError(f"GraphQL errors: {payload['errors']}")
    return payload["data"]


def download_uniswap_v2_pool_data(config: PipelineConfig) -> pd.DataFrame:
    """Download Uniswap V2 WETH/USDC pair snapshots.

    The default endpoint is the legacy public Uniswap V2 subgraph. If your The Graph
    setup uses the gateway, set THEGRAPH_UNISWAP_V2_ENDPOINT explicitly in `.env`.
    """
    ensure_dirs()
    start_ts = _to_unix(config.start)
    end_ts = _to_unix(config.end)
    pair = config.uniswap_v2_pair.lower()

    rows: list[dict[str, Any]] = []
    cursor = start_ts
    batch_size = 1000

    # pairHourDatas gives hourly data. For daily frequency we still download hourly
    # and aggregate later in build_dataset.py.
    query = """
    query PairHours($pair: String!, $cursor: Int!, $end: Int!, $first: Int!) {
      pairHourDatas(
        first: $first,
        orderBy: hourStartUnix,
        orderDirection: asc,
        where: { pair: $pair, hourStartUnix_gte: $cursor, hourStartUnix_lte: $end }
      ) {
        hourStartUnix
        hourlyVolumeUSD
        reserveUSD
        totalSupply
        reserve0
        reserve1
      }
    }
    """

    while cursor <= end_ts:
        data = _post_graphql(
            config.thegraph_uniswap_endpoint,
            query,
            {"pair": pair, "cursor": cursor, "end": end_ts, "first": batch_size},
        )
        batch = data.get("pairHourDatas") or []
        if not batch:
            break
        rows.extend(batch)
        last = int(batch[-1]["hourStartUnix"])
        next_cursor = last + 3600
        if next_cursor <= cursor or len(batch) < batch_size:
            break
        cursor = next_cursor

    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(
            columns=["timestamp", "uni_tvl_usd", "uni_volume_usd", "uni_fees_usd", "uni_liquidity"]
        )
    else:
        df["timestamp"] = pd.to_datetime(df["hourStartUnix"].astype(int), unit="s", utc=True)
        df["uni_volume_usd"] = df["hourlyVolumeUSD"].astype(float)
        df["uni_tvl_usd"] = df["reserveUSD"].astype(float)
        df["uni_liquidity"] = df["totalSupply"].astype(float)
        df["uni_fees_usd"] = df["uni_volume_usd"] * config.uniswap_fee_rate
        df = df[["timestamp", "uni_tvl_usd", "uni_volume_usd", "uni_fees_usd", "uni_liquidity"]]
        df = df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)

    config.raw_uniswap_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.raw_uniswap_path, index=False)
    return df
