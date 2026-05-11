from __future__ import annotations

import argparse

from research.data_pipeline.build_dataset import build_market_dataset
from research.data_pipeline.config import build_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2025-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--frequency", choices=["hourly", "daily"], default="hourly")
    args = parser.parse_args()

    config = build_config(args.start, args.end, args.frequency)
    df = build_market_dataset(config)
    print(f"Saved {len(df)} rows to {config.processed_market_data_path}")


if __name__ == "__main__":
    main()
