from __future__ import annotations

import numpy as np
import pandas as pd


def add_regime_labels(
    df: pd.DataFrame,
    price_col: str = "eth_price_usdc",
    window: int = 24,
    trend_threshold: float = 0.05,
    vol_threshold: float = 0.04,
) -> pd.DataFrame:
    """Add simple rule-based market regimes.

    For daily data, pass a smaller window such as 7 or 14 from caller if needed.
    """
    out = df.copy()
    out["returns"] = out[price_col].pct_change()
    out["rolling_return"] = out[price_col].pct_change(window)
    out["rolling_vol"] = out["returns"].rolling(window).std() * np.sqrt(window)

    def label(row: pd.Series) -> str:
        rr = row.get("rolling_return")
        rv = row.get("rolling_vol")
        if pd.isna(rr) or pd.isna(rv):
            return "warmup"
        if rr > trend_threshold:
            return "uptrend"
        if rr < -trend_threshold:
            return "downtrend"
        if abs(rr) <= trend_threshold and rv > vol_threshold:
            return "high_vol_chop"
        return "sideways"

    out["regime"] = out.apply(label, axis=1)
    return out.drop(columns=["returns", "rolling_return", "rolling_vol"])
