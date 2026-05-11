import pandas as pd

from research.data_pipeline.regimes import add_regime_labels


def test_regime_labels_are_added():
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=30, freq="h", tz="UTC"),
            "eth_price_usdc": [2000 + i * 10 for i in range(30)],
        }
    )
    result = add_regime_labels(df, window=5)
    assert "regime" in result.columns
    assert result["regime"].notna().all()


def test_regime_labels_are_from_expected_set():
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=30, freq="h", tz="UTC"),
            "eth_price_usdc": [2000 + (-1) ** i * 50 for i in range(30)],
        }
    )
    result = add_regime_labels(df, window=5)
    allowed = {"warmup", "uptrend", "downtrend", "high_vol_chop", "sideways"}
    assert set(result["regime"]).issubset(allowed)
