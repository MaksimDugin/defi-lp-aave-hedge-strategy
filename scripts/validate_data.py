from __future__ import annotations

import argparse

from research.data_pipeline.config import PROCESSED_ROOT
from research.data_pipeline.validate import validate_market_data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default=str(PROCESSED_ROOT / "market_data.csv"))
    args = parser.parse_args()

    validate_market_data(args.path)
    print(f"Validation passed: {args.path}")


if __name__ == "__main__":
    main()
