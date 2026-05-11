from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PROJECT_ROOT.parent
DATA_ROOT = REPO_ROOT / "data"
RAW_ROOT = DATA_ROOT / "raw"
PROCESSED_ROOT = DATA_ROOT / "processed"
ASSUMPTIONS_PATH = PROJECT_ROOT / "assumptions.yaml"

Frequency = Literal["hourly", "daily"]


def parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class PipelineConfig:
    start: datetime
    end: datetime
    frequency: Frequency = "hourly"

    # Mainnet addresses used for historical data.
    uniswap_v2_pair: str = "0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc"
    weth: str = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    usdc: str = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    aave_v3_market: str = "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
    chain_id: int = 1

    # API endpoints / keys.
    thegraph_uniswap_endpoint: str = os.getenv(
        "THEGRAPH_UNISWAP_V2_ENDPOINT",
        "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2",
    )
    thegraph_api_key: str | None = os.getenv("THEGRAPH_API_KEY")
    coingecko_api_key: str | None = os.getenv("COINGECKO_API_KEY")
    aave_graphql_endpoint: str = "https://api.v3.aave.com/graphql"

    # Assumptions.
    uniswap_fee_rate: float = 0.003
    gas_cost_usdc: float = 15.0

    @property
    def raw_uniswap_path(self) -> Path:
        return RAW_ROOT / "uniswap" / f"uniswap_v2_weth_usdc_{self.frequency}.csv"

    @property
    def raw_aave_path(self) -> Path:
        return RAW_ROOT / "aave" / f"aave_v3_rates_{self.frequency}.csv"

    @property
    def raw_prices_path(self) -> Path:
        return RAW_ROOT / "prices" / f"eth_usdc_price_{self.frequency}.csv"

    @property
    def processed_market_data_path(self) -> Path:
        name = "market_data.csv" if self.frequency == "hourly" else "market_data_daily.csv"
        return PROCESSED_ROOT / name


def load_assumptions() -> dict:
    if not ASSUMPTIONS_PATH.exists():
        return {}
    with ASSUMPTIONS_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_config(start: str, end: str, frequency: Frequency = "hourly") -> PipelineConfig:
    assumptions = load_assumptions()
    costs = assumptions.get("costs", {})
    addresses = assumptions.get("addresses_mainnet", {})
    return PipelineConfig(
        start=parse_date(start),
        end=parse_date(end),
        frequency=frequency,
        uniswap_v2_pair=addresses.get(
            "uniswap_v2_weth_usdc_pair",
            "0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc",
        ),
        weth=addresses.get("weth", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
        usdc=addresses.get("usdc", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"),
        aave_v3_market=addresses.get(
            "aave_v3_market",
            "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
        ),
        uniswap_fee_rate=float(costs.get("uniswap_v2_fee_rate", 0.003)),
        gas_cost_usdc=float(costs.get("gas_cost_per_rebalance_usdc", 15.0)),
    )


def ensure_dirs() -> None:
    for p in [RAW_ROOT / "uniswap", RAW_ROOT / "aave", RAW_ROOT / "prices", PROCESSED_ROOT]:
        p.mkdir(parents=True, exist_ok=True)
