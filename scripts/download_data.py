from __future__ import annotations

import argparse

from research.data_pipeline.config import build_config
from research.data_pipeline.download_aave import download_aave_v3_rates
from research.data_pipeline.download_prices import download_eth_price_coingecko
from research.data_pipeline.download_uniswap import download_uniswap_v2_pool_data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--frequency", choices=["hourly", "daily"], default="hourly")
    parser.add_argument("--skip-uniswap", action="store_true")
    parser.add_argument("--skip-aave", action="store_true")
    parser.add_argument("--skip-prices", action="store_true")
    args = parser.parse_args()

    config = build_config(args.start, args.end, args.frequency)

    if not args.skip_prices:
        print("Downloading ETH price data...")
        download_eth_price_coingecko(config)
    if not args.skip_uniswap:
        print("Downloading Uniswap V2 pool data...")
        download_uniswap_v2_pool_data(config)
    if not args.skip_aave:
        print("Downloading Aave V3 rates...")
        download_aave_v3_rates(config)

    print("Done.")


if __name__ == "__main__":
    main()
