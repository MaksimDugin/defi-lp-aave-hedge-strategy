def compute_strategy_fees(
    pool_fees_usdc: float,
    lp_share: float,
) -> float:
    """
    Compute strategy fee share from total pool fees.
    """

    return pool_fees_usdc * lp_share