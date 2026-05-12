from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


# config.py лежит в:
# repo/research/data_pipeline/config.py
# поэтому parents[2] = repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_ROOT = PROJECT_ROOT / "data" / "processed"
RAW_ROOT = PROJECT_ROOT / "data" / "raw"

load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=True)


def _parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class PipelineConfig:
    start: datetime
    end: datetime
    frequency: str

    project_root: Path
    data_dir: Path
    raw_dir: Path
    processed_dir: Path

    raw_prices_path: Path
    raw_uniswap_path: Path
    raw_aave_path: Path

    processed_market_data_path: Path
    processed_market_data_daily_path: Path
    processed_regimes_path: Path

    thegraph_api_key: str
    coingecko_api_key: str
    eth_rpc_url: str
    etherscan_api_key: str

    uniswap_v2_pair: str
    uniswap_v2_fee_rate: float
    uniswap_v2_subgraph_id: str
    uniswap_v2_graphql_endpoint: str

    aave_graphql_endpoint: str
    aave_v3_market: str
    weth_address: str
    usdc_address: str

    gas_cost_usdc: float

    # aliases for compatibility with existing scripts
    @property
    def raw_uniswap_v2_path(self) -> Path:
        return self.raw_uniswap_path

    @property
    def raw_aave_rates_path(self) -> Path:
        return self.raw_aave_path

    @property
    def aave_v3_graphql_endpoint(self) -> str:
        return self.aave_graphql_endpoint


def ensure_dirs() -> None:
    for path in [
        PROJECT_ROOT / "data" / "raw" / "prices",
        PROJECT_ROOT / "data" / "raw" / "uniswap",
        PROJECT_ROOT / "data" / "raw" / "aave",
        PROJECT_ROOT / "data" / "processed",
        PROJECT_ROOT / "reports" / "figures",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def build_config(start: str, end: str, frequency: str) -> PipelineConfig:
    if frequency not in {"hourly", "daily"}:
        raise ValueError("frequency must be either 'hourly' or 'daily'")

    ensure_dirs()

    thegraph_api_key = os.getenv("THEGRAPH_API_KEY", "").strip()
    coingecko_api_key = os.getenv("COINGECKO_API_KEY", "").strip()
    eth_rpc_url = os.getenv("ETH_RPC_URL", "").strip()
    etherscan_api_key = os.getenv("ETHERSCAN_API_KEY", "").strip()

    # Uniswap V2 WETH/USDC mainnet pair
    uniswap_v2_pair = "0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc"

    # Current Uniswap V2 mainnet subgraph ID from Uniswap docs
    uniswap_v2_subgraph_id = "A3Np3RQbaBA6oKJgiwDJeo5T3zrYfGHPWFYayMwtNDum"

    if not thegraph_api_key:
        raise RuntimeError(
            "THEGRAPH_API_KEY is missing. Add it to .env as THEGRAPH_API_KEY=..."
        )

    uniswap_v2_graphql_endpoint = (
        f"https://gateway.thegraph.com/api/{thegraph_api_key}/subgraphs/id/"
        f"{uniswap_v2_subgraph_id}"
    )

    data_dir = PROJECT_ROOT / "data"
    raw_dir = data_dir / "raw"
    processed_dir = data_dir / "processed"

    return PipelineConfig(
        start=_parse_date(start),
        end=_parse_date(end),
        frequency=frequency,

        project_root=PROJECT_ROOT,
        data_dir=data_dir,
        raw_dir=raw_dir,
        processed_dir=processed_dir,

        raw_prices_path=raw_dir / "prices" / f"eth_usdc_price_{frequency}.csv",
        raw_uniswap_path=raw_dir / "uniswap" / f"uniswap_v2_weth_usdc_{frequency}.csv",
        raw_aave_path=raw_dir / "aave" / f"aave_v3_rates_{frequency}.csv",

        processed_market_data_path=processed_dir / "market_data.csv",
        processed_market_data_daily_path=processed_dir / "market_data_daily.csv",
        processed_regimes_path=processed_dir / "regimes.csv",

        thegraph_api_key=thegraph_api_key,
        coingecko_api_key=coingecko_api_key,
        eth_rpc_url=eth_rpc_url,
        etherscan_api_key=etherscan_api_key,

        uniswap_v2_pair=uniswap_v2_pair,
        uniswap_v2_fee_rate=0.003,
        uniswap_v2_subgraph_id=uniswap_v2_subgraph_id,
        uniswap_v2_graphql_endpoint=uniswap_v2_graphql_endpoint,

        aave_graphql_endpoint="https://api.v3.aave.com/graphql",
        aave_v3_market="0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
        weth_address="0xC02aaA39b223Fe8d0A0E5C4F27eAD9083C756Cc2",
        usdc_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",

        gas_cost_usdc=15.0,
    )