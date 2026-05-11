from __future__ import annotations

import pandas as pd


def read_csv_timestamp(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def resample_market_df(df: pd.DataFrame, frequency: str) -> pd.DataFrame:
    rule = "1h" if frequency == "hourly" else "1D"
    if df.empty:
        return df
    out = df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
    out = out.sort_values("timestamp").set_index("timestamp")

    agg = {}
    for col in out.columns:
        if col.endswith("volume_usd") or col.endswith("fees_usd"):
            agg[col] = "sum"
        else:
            agg[col] = "last"
    out = out.resample(rule).agg(agg).ffill().reset_index()
    return out


def merge_on_timestamp(frames: list[pd.DataFrame]) -> pd.DataFrame:
    frames = [df.copy() for df in frames if df is not None and not df.empty]
    if not frames:
        return pd.DataFrame()
    base = frames[0].sort_values("timestamp")
    for df in frames[1:]:
        base = base.merge(df.sort_values("timestamp"), on="timestamp", how="outer")
    return base.sort_values("timestamp").reset_index(drop=True)


def clean_market_data(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
    out = out.sort_values("timestamp").drop_duplicates("timestamp")
    out = out.dropna(subset=["eth_price_usdc", "uni_tvl_usd", "uni_volume_usd"])

    rate_cols = ["aave_weth_borrow_rate", "aave_usdc_supply_rate"]
    for col in rate_cols:
        if col in out.columns:
            out[col] = out[col].ffill().fillna(0.0)

    if "gas_cost_usdc" not in out.columns:
        out["gas_cost_usdc"] = 15.0

    return out.reset_index(drop=True)
