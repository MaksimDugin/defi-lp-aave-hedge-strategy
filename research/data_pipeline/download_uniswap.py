from __future__ import annotations

import time
from typing import Any

import pandas as pd
import requests

from research.data_pipeline.config import PipelineConfig, ensure_dirs


def _post_graphql_with_retry(
    endpoint: str,
    query: str,
    variables: dict[str, Any],
    retries: int = 5,
    timeout: int = 120,
    sleep_seconds: float = 2.0,
) -> dict[str, Any]:
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(
                endpoint,
                json={"query": query, "variables": variables},
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()

            if "errors" in payload:
                raise RuntimeError(f"GraphQL errors: {payload['errors']}")

            return payload["data"]

        except Exception as exc:
            last_error = exc
            if attempt == retries:
                break

            wait = sleep_seconds * attempt
            print(f"Uniswap GraphQL request failed, retry {attempt}/{retries}: {exc}")
            time.sleep(wait)

    raise RuntimeError(f"Uniswap GraphQL request failed after {retries} retries") from last_error


def _hourly_query() -> str:
    return """
    query PairHourDatas($pair: Bytes!, $cursor: Int!, $limit: Int!) {
      pairHourDatas(
        first: $limit
        orderBy: hourStartUnix
        orderDirection: asc
        where: {
          pair: $pair
          hourStartUnix_gte: $cursor
        }
      ) {
        hourStartUnix
        reserveUSD
        hourlyVolumeUSD
        totalSupply
      }
    }
    """


def _daily_query() -> str:
    return """
    query PairDayDatas($pair: Bytes!, $cursor: Int!, $limit: Int!) {
      pairDayDatas(
        first: $limit
        orderBy: date
        orderDirection: asc
        where: {
          pairAddress: $pair
          date_gte: $cursor
        }
      ) {
        date
        reserveUSD
        dailyVolumeUSD
        totalSupply
      }
    }
    """


def download_uniswap_v2_pool_data(config: PipelineConfig) -> pd.DataFrame:
    """
    Download Uniswap V2 WETH/USDC pool data from The Graph.

    Output columns:
    - timestamp
    - uni_tvl_usd
    - uni_volume_usd
    - uni_fees_usd
    - uni_liquidity
    """
    ensure_dirs()
    if config.raw_uniswap_path.exists() and config.raw_uniswap_path.stat().st_size > 0:
        print(f"Loading existing Uniswap data: {config.raw_uniswap_path}")
        df = pd.read_csv(config.raw_uniswap_path, parse_dates=["timestamp"])
        print(f"Loaded {len(df)} rows from existing file")
        return df

    pair = config.uniswap_v2_pair.lower()
    start_ts = int(config.start.timestamp())
    end_ts = int(config.end.timestamp())

    # Smaller batch size avoids The Graph read timeouts.
    limit = 200

    rows: list[dict[str, Any]] = []
    cursor = start_ts

    if config.frequency == "hourly":
        query = _hourly_query()
        node_name = "pairHourDatas"
        ts_col = "hourStartUnix"
        volume_col = "hourlyVolumeUSD"
        step = 3600
    elif config.frequency == "daily":
        query = _daily_query()
        node_name = "pairDayDatas"
        ts_col = "date"
        volume_col = "dailyVolumeUSD"
        step = 86400
    else:
        raise ValueError(f"Unsupported frequency: {config.frequency}")

    while cursor <= end_ts:
        variables = {
            "pair": pair,
            "cursor": cursor,
            "limit": limit,
        }

        data = _post_graphql_with_retry(
            endpoint=config.uniswap_v2_graphql_endpoint,
            query=query,
            variables=variables,
            retries=5,
            timeout=120,
            sleep_seconds=2.0,
        )

        batch = data.get(node_name, [])

        if not batch:
            break

        rows.extend(batch)

        last_ts = int(batch[-1][ts_col])
        next_cursor = last_ts + step

        print(
            f"Downloaded Uniswap {config.frequency}: "
            f"{len(rows)} rows, last timestamp={last_ts}"
        )

        if next_cursor <= cursor:
            break

        cursor = next_cursor

        if cursor > end_ts:
            break

        # Be polite to gateway.
        time.sleep(0.15)

    if not rows:
        df = pd.DataFrame(
            columns=[
                "timestamp",
                "uni_tvl_usd",
                "uni_volume_usd",
                "uni_fees_usd",
                "uni_liquidity",
            ]
        )
    else:
        df = pd.DataFrame(rows)

        df["timestamp"] = pd.to_datetime(df[ts_col].astype(int), unit="s", utc=True)
        df["uni_tvl_usd"] = df["reserveUSD"].astype(float)
        df["uni_volume_usd"] = df[volume_col].astype(float)
        df["uni_fees_usd"] = df["uni_volume_usd"] * config.uniswap_v2_fee_rate
        df["uni_liquidity"] = df["totalSupply"].astype(float)

        df = (
            df[
                [
                    "timestamp",
                    "uni_tvl_usd",
                    "uni_volume_usd",
                    "uni_fees_usd",
                    "uni_liquidity",
                ]
            ]
            .dropna()
            .drop_duplicates("timestamp")
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

        df = df[df["timestamp"] >= pd.Timestamp(config.start)]
        df = df[df["timestamp"] <= pd.Timestamp(config.end)]

    config.raw_uniswap_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.raw_uniswap_path, index=False)

    print(f"Saved Uniswap V2 pool data: {config.raw_uniswap_path} ({len(df)} rows)")

    return df