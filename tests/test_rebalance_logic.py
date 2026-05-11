def should_rebalance(target_debt, current_debt, lp_delta, threshold):
    if lp_delta <= 0:
        return False
    hedge_error = abs(target_debt - current_debt) / lp_delta
    return hedge_error > threshold


def test_rebalance_triggered_when_error_above_threshold():
    assert should_rebalance(
        target_debt=7.5,
        current_debt=6.0,
        lp_delta=10.0,
        threshold=0.10,
    )


def test_rebalance_not_triggered_when_error_below_threshold():
    assert not should_rebalance(
        target_debt=7.5,
        current_debt=7.0,
        lp_delta=10.0,
        threshold=0.10,
    )


def test_rebalance_not_triggered_when_lp_delta_zero():
    assert not should_rebalance(
        target_debt=0.0,
        current_debt=0.0,
        lp_delta=0.0,
        threshold=0.10,
    )
