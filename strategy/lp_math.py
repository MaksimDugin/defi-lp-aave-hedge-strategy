def compute_lp_value(
    pool_tvl_usdc: float,
    lp_share: float,
) -> float:
    """
    LP position value from pool TVL.
    """

    return pool_tvl_usdc * lp_share