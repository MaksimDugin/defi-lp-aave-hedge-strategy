from __future__ import annotations

import os
import time
from datetime import timedelta
from typing import Any

import pandas as pd
import requests

from research.data_pipeline.config import PipelineConfig, ensure_dirs


# Aave V3 Ethereum Pool
AAVE_V3_ETHEREUM_POOL = "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2"

# Underlying reserve addresses on Ethereum
WETH_RESERVE_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
USDC_RESERVE_ADDRESS = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"

# ReserveDataUpdated(
#   address indexed reserve,
#   uint256 liquidityRate,
#   uint256 stableBorrowRate,
#   uint256 variableBorrowRate,
#   uint256 liquidityIndex,
#   uint256 variableBorrowIndex
# )
RESERVE_DATA_UPDATED_TOPIC0 = (
    "0x804c9b842b2748a22bb64b345453a3de7ca54a6ca45ce00d415894979e22897a"
)

RAY = 10**27

OUTPUT_COLUMNS = [
    "timestamp",
    "aave_weth_borrow_rate",
    "aave_usdc_supply_rate",
]


def _periods_per_year(frequency: str) -> int:
    if frequency == "hourly":
        return 365 * 24
    if frequency == "daily":
        return 365
    raise ValueError(f"Unsupported frequency: {frequency}")


def _as_utc_timestamp(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)

    if ts.tzinfo is None:
        return ts.tz_localize("UTC")

    return ts.tz_convert("UTC")


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
                start=_as_utc_timestamp(config.start),
                end=_as_utc_timestamp(config.end),
                freq=freq,
            )
        }
    )


def _address_to_topic(address: str) -> str:
    normalized = address.lower().replace("0x", "")
    return "0x" + ("0" * 24) + normalized


def _topic_to_address(topic: str) -> str:
    return "0x" + topic[-40:]


def _get_rpc_url() -> str:
    return (
        os.getenv("ETHEREUM_RPC_URL")
        or os.getenv("ETH_RPC_URL")
        or "https://eth.llamarpc.com"
    )

def _assert_ethereum_mainnet(rpc_url: str) -> None:
    chain_id_hex = _rpc_call(rpc_url, "eth_chainId", [])
    chain_id = int(chain_id_hex, 16)

    if chain_id != 1:
        raise RuntimeError(
            f"RPC must point to Ethereum mainnet, got chainId={chain_id}. "
            "Use https://mainnet.infura.io/v3/<API_KEY>, not Sepolia."
        )


def _rpc_call(
    rpc_url: str,
    method: str,
    params: list[Any],
    retries: int = 5,
    timeout: int = 60,
    sleep_seconds: float = 1.5,
) -> Any:
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": method,
                    "params": params,
                },
                timeout=timeout,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "aave-rates-backtest/1.0",
                },
            )
            response.raise_for_status()
            payload = response.json()

            if "error" in payload:
                raise RuntimeError(payload["error"])

            return payload["result"]

        except Exception as exc:
            last_error = exc

            if attempt == retries:
                break

            wait = sleep_seconds * attempt
            print(f"RPC request failed, retry {attempt}/{retries}: {exc}")
            time.sleep(wait)

    raise RuntimeError(f"RPC request failed after {retries} retries") from last_error


def _rpc_batch_call(
    rpc_url: str,
    calls: list[tuple[str, list[Any]]],
    retries: int = 5,
    timeout: int = 90,
    sleep_seconds: float = 1.5,
) -> list[Any]:
    if not calls:
        return []

    last_error: Exception | None = None

    request_payload = [
        {
            "jsonrpc": "2.0",
            "id": i,
            "method": method,
            "params": params,
        }
        for i, (method, params) in enumerate(calls)
    ]

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(
                rpc_url,
                json=request_payload,
                timeout=timeout,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "aave-rates-backtest/1.0",
                },
            )
            response.raise_for_status()
            payload = response.json()

            if not isinstance(payload, list):
                raise RuntimeError("Unexpected batch RPC response")

            payload_by_id = {item["id"]: item for item in payload}
            result: list[Any] = []

            for i in range(len(calls)):
                item = payload_by_id[i]

                if "error" in item:
                    raise RuntimeError(item["error"])

                result.append(item["result"])

            return result

        except Exception as exc:
            last_error = exc

            if attempt == retries:
                break

            wait = sleep_seconds * attempt
            print(f"Batch RPC request failed, retry {attempt}/{retries}: {exc}")
            time.sleep(wait)

    raise RuntimeError("Batch RPC request failed after retries") from last_error


def _get_block_timestamp(rpc_url: str, block_number: int) -> int:
    block = _rpc_call(
        rpc_url,
        "eth_getBlockByNumber",
        [hex(block_number), False],
    )

    if block is None:
        raise RuntimeError(f"Block not found: {block_number}")

    return int(block["timestamp"], 16)


def _find_first_block_at_or_after_timestamp(
    rpc_url: str,
    target_timestamp: int,
) -> int:
    latest_block = int(_rpc_call(rpc_url, "eth_blockNumber", []), 16)

    low = 0
    high = latest_block

    while low < high:
        mid = (low + high) // 2
        mid_timestamp = _get_block_timestamp(rpc_url, mid)

        if mid_timestamp < target_timestamp:
            low = mid + 1
        else:
            high = mid

    return low


def _get_block_timestamps_batch(
    rpc_url: str,
    block_numbers: list[int],
    batch_size: int = 100,
) -> dict[int, pd.Timestamp]:
    out: dict[int, pd.Timestamp] = {}

    unique_blocks = sorted(set(block_numbers))

    for i in range(0, len(unique_blocks), batch_size):
        batch = unique_blocks[i : i + batch_size]

        calls = [
            ("eth_getBlockByNumber", [hex(block_number), False])
            for block_number in batch
        ]

        results = _rpc_batch_call(rpc_url, calls)

        for block_number, block in zip(batch, results):
            if block is None:
                raise RuntimeError(f"Block not found: {block_number}")

            timestamp = int(block["timestamp"], 16)
            out[block_number] = pd.to_datetime(timestamp, unit="s", utc=True)

    return out


def _get_reserve_data_updated_logs(
    rpc_url: str,
    from_block: int,
    to_block: int,
    max_block_span: int,
) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = []

    reserve_topics = [
        _address_to_topic(WETH_RESERVE_ADDRESS),
        _address_to_topic(USDC_RESERVE_ADDRESS),
    ]

    cursor = from_block
    current_span = max_block_span

    while cursor <= to_block:
        chunk_to = min(cursor + current_span - 1, to_block)

        params = [
            {
                "address": AAVE_V3_ETHEREUM_POOL,
                "fromBlock": hex(cursor),
                "toBlock": hex(chunk_to),
                "topics": [
                    RESERVE_DATA_UPDATED_TOPIC0,
                    reserve_topics,
                ],
            }
        ]

        try:
            chunk_logs = _rpc_call(
                rpc_url,
                "eth_getLogs",
                params,
                retries=3,
                timeout=90,
            )

            logs.extend(chunk_logs)

            print(
                f"Fetched Aave logs: blocks {cursor}-{chunk_to}, "
                f"logs={len(chunk_logs)}"
            )

            cursor = chunk_to + 1
            current_span = max_block_span

        except Exception as exc:
            if current_span <= 1:
                raise

            current_span = max(1, current_span // 2)

            print(
                f"RPC log range failed for blocks {cursor}-{chunk_to}: {exc}. "
                f"Reducing block span to {current_span}"
            )

    return logs


def _decode_reserve_data_updated_logs(
    rpc_url: str,
    logs: list[dict[str, Any]],
) -> pd.DataFrame:
    if not logs:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "reserve",
                "liquidity_apr",
                "variable_borrow_apr",
            ]
        )

    block_numbers = [int(log["blockNumber"], 16) for log in logs]
    block_timestamps = _get_block_timestamps_batch(rpc_url, block_numbers)

    rows: list[dict[str, Any]] = []

    for log in logs:
        topics = log["topics"]
        data = log["data"].replace("0x", "")

        if len(topics) < 2:
            continue

        reserve = _topic_to_address(topics[1]).lower()

        words = [
            int(data[i : i + 64], 16)
            for i in range(0, len(data), 64)
        ]

        if len(words) < 5:
            continue

        liquidity_rate = words[0]
        variable_borrow_rate = words[2]

        block_number = int(log["blockNumber"], 16)

        rows.append(
            {
                "timestamp": block_timestamps[block_number],
                "reserve": reserve,
                "liquidity_apr": liquidity_rate / RAY,
                "variable_borrow_apr": variable_borrow_rate / RAY,
                "block_number": block_number,
                "log_index": int(log["logIndex"], 16),
            }
        )

    return (
        pd.DataFrame(rows)
        .sort_values(["timestamp", "block_number", "log_index"])
        .reset_index(drop=True)
    )


def _filter_window(df: pd.DataFrame, config: PipelineConfig) -> pd.DataFrame:
    if df.empty:
        return df

    start = _as_utc_timestamp(config.start)
    end = _as_utc_timestamp(config.end)

    return df[(df["timestamp"] >= start) & (df["timestamp"] <= end)].reset_index(
        drop=True
    )


def _fill_rate_column(series: pd.Series, column_name: str) -> pd.Series:
    missing = int(series.isna().sum())

    if missing > 0:
        print(
            f"{column_name}: filling {missing} missing values "
            "with forward-fill, then back-fill"
        )

    filled = series.ffill().bfill()

    if filled.isna().any():
        raise RuntimeError(f"Could not fill missing values for {column_name}")

    return filled


def _build_rates_from_onchain_events(config: PipelineConfig) -> pd.DataFrame:
    rpc_url = _get_rpc_url()
    _assert_ethereum_mainnet(rpc_url)
    periods = _periods_per_year(config.frequency)

    start = _as_utc_timestamp(config.start)
    end = _as_utc_timestamp(config.end)

    lookback_days = int(os.getenv("AAVE_EVENT_LOOKBACK_DAYS", "14"))
    max_block_span = int(os.getenv("AAVE_RPC_MAX_BLOCK_SPAN", "10000"))

    scan_start = start - pd.Timedelta(days=lookback_days)

    print(f"Using Ethereum RPC: {rpc_url}")
    print(f"Finding start block for {scan_start.isoformat()}...")
    from_block = _find_first_block_at_or_after_timestamp(
        rpc_url,
        int(scan_start.timestamp()),
    )

    print(f"Finding end block for {end.isoformat()}...")
    to_block = _find_first_block_at_or_after_timestamp(
        rpc_url,
        int(end.timestamp()),
    )

    print(f"Scanning Aave V3 ReserveDataUpdated logs: {from_block}-{to_block}")

    logs = _get_reserve_data_updated_logs(
        rpc_url=rpc_url,
        from_block=from_block,
        to_block=to_block,
        max_block_span=max_block_span,
    )

    events = _decode_reserve_data_updated_logs(rpc_url, logs)

    if events.empty:
        raise RuntimeError("No Aave ReserveDataUpdated logs found")

    weth_address = WETH_RESERVE_ADDRESS.lower()
    usdc_address = USDC_RESERVE_ADDRESS.lower()

    weth_events = events[events["reserve"] == weth_address].copy()
    usdc_events = events[events["reserve"] == usdc_address].copy()

    if weth_events.empty:
        raise RuntimeError("No WETH ReserveDataUpdated logs found")

    if usdc_events.empty:
        raise RuntimeError("No USDC ReserveDataUpdated logs found")

    weth_events = (
        weth_events[["timestamp", "variable_borrow_apr"]]
        .drop_duplicates("timestamp", keep="last")
        .sort_values("timestamp")
        .rename(columns={"variable_borrow_apr": "aave_weth_borrow_apr"})
    )

    usdc_events = (
        usdc_events[["timestamp", "liquidity_apr"]]
        .drop_duplicates("timestamp", keep="last")
        .sort_values("timestamp")
        .rename(columns={"liquidity_apr": "aave_usdc_supply_apr"})
    )

    output = _make_output_timeline(config).sort_values("timestamp")

    output = pd.merge_asof(
        output,
        weth_events,
        on="timestamp",
        direction="backward",
    )

    output = pd.merge_asof(
        output.sort_values("timestamp"),
        usdc_events,
        on="timestamp",
        direction="backward",
    )

    output["aave_weth_borrow_apr"] = _fill_rate_column(
        output["aave_weth_borrow_apr"],
        "aave_weth_borrow_apr",
    )
    output["aave_usdc_supply_apr"] = _fill_rate_column(
        output["aave_usdc_supply_apr"],
        "aave_usdc_supply_apr",
    )

    output["aave_weth_borrow_rate"] = output["aave_weth_borrow_apr"] / periods
    output["aave_usdc_supply_rate"] = output["aave_usdc_supply_apr"] / periods

    return output[OUTPUT_COLUMNS].copy()


def _validate_output(df: pd.DataFrame) -> pd.DataFrame:
    missing = set(OUTPUT_COLUMNS) - set(df.columns)

    if missing:
        raise RuntimeError(f"Aave rates output missing columns: {missing}")

    out = df[OUTPUT_COLUMNS].copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)

    for column in ["aave_weth_borrow_rate", "aave_usdc_supply_rate"]:
        out[column] = pd.to_numeric(out[column], errors="coerce")

    if out[OUTPUT_COLUMNS].isna().any().any():
        raise RuntimeError("Aave rates output contains NaN values")

    return (
        out.drop_duplicates("timestamp")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )


def download_aave_v3_rates(config: PipelineConfig) -> pd.DataFrame:
    """
    Download Aave V3 Ethereum WETH borrow and USDC supply rates from on-chain
    ReserveDataUpdated events via Ethereum JSON-RPC.

    Output file:
    data/raw/aave/aave_v3_rates_hourly.csv

    Output columns:
    - timestamp
    - aave_weth_borrow_rate
    - aave_usdc_supply_rate

    Rates are per-period decimal rates, not annual APR.

    Environment variables:
    - ETHEREUM_RPC_URL:
        Optional Ethereum RPC URL. If absent, uses public LlamaRPC.
    - AAVE_EVENT_LOOKBACK_DAYS:
        How many days before config.start to scan, default 14.
        This helps fill the first backtest timestamp with the latest known rate.
    - AAVE_RPC_MAX_BLOCK_SPAN:
        Max eth_getLogs block span, default 10000.
        Lower it if your RPC provider rejects large log ranges.
    """
    ensure_dirs()

    if config.raw_aave_path.exists() and config.raw_aave_path.stat().st_size > 0:
        print(f"Loading existing Aave data: {config.raw_aave_path}")
        df = pd.read_csv(config.raw_aave_path, parse_dates=["timestamp"])
        df = _validate_output(df)
        print(f"Loaded {len(df)} rows from existing file")
        return df

    df = _build_rates_from_onchain_events(config)
    df = _validate_output(df)

    config.raw_aave_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.raw_aave_path, index=False)

    print(f"Saved Aave V3 on-chain rates: {config.raw_aave_path} ({len(df)} rows)")

    return df