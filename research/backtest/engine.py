from strategy.lp_math import compute_lp_value
from strategy.fees import compute_strategy_fees


def update_lp_position(
    state,
    market_row,
):
    """
    Update LP valuation and fees.
    """

    lp_value = compute_lp_value(
        pool_tvl_usdc=market_row["uni_tvl_usd"],
        lp_share=state.lp_share,
    )

    strategy_fees = compute_strategy_fees(
        pool_fees_usdc=market_row["uni_fees_usd"],
        lp_share=state.lp_share,
    )

    state.lp_value_usdc = lp_value

    state.fees_collected_usdc += strategy_fees

    state.equity_usdc = (
        state.cash_usdc
        + state.lp_value_usdc
        - state.weth_debt_usdc
    )

    return state