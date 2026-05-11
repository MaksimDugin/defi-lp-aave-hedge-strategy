from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default="data/processed/market_data.csv")
    parser.add_argument("--out", default="reports/figures")
    args = parser.parse_args()

    df = pd.read_csv(args.path, parse_dates=["timestamp"])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    plots = [
        ("eth_price_usdc", "ETH/USDC price", "eth_price.png"),
        ("uni_tvl_usd", "Uniswap V2 TVL", "uniswap_tvl.png"),
        ("uni_volume_usd", "Uniswap V2 volume", "uniswap_volume.png"),
        ("uni_fees_usd", "Estimated LP fees", "uniswap_fees.png"),
        ("aave_weth_borrow_rate", "Aave WETH borrow rate per period", "aave_weth_borrow_rate.png"),
        ("aave_usdc_supply_rate", "Aave USDC supply rate per period", "aave_usdc_supply_rate.png"),
    ]
    for col, title, filename in plots:
        plt.figure(figsize=(10, 4))
        plt.plot(df["timestamp"], df[col])
        plt.title(title)
        plt.xlabel("timestamp")
        plt.ylabel(col)
        plt.tight_layout()
        plt.savefig(out / filename, dpi=160)
        plt.close()

    print(f"Saved figures to {out}")


if __name__ == "__main__":
    main()
