def calculate_nav(lp_value, aave_collateral, aave_debt, idle_value, cumulative_costs):
    return lp_value + aave_collateral - aave_debt + idle_value - cumulative_costs


def test_nav_includes_lp_collateral_debt_idle_and_costs():
    nav = calculate_nav(
        lp_value=50000.0,
        aave_collateral=50000.0,
        aave_debt=15000.0,
        idle_value=2000.0,
        cumulative_costs=100.0,
    )
    assert nav == 86900.0


def test_nav_decreases_when_debt_increases():
    nav_low_debt = calculate_nav(50000.0, 50000.0, 10000.0, 0.0, 0.0)
    nav_high_debt = calculate_nav(50000.0, 50000.0, 20000.0, 0.0, 0.0)
    assert nav_high_debt < nav_low_debt


def test_nav_decreases_when_costs_increase():
    nav_low_cost = calculate_nav(50000.0, 50000.0, 10000.0, 0.0, 100.0)
    nav_high_cost = calculate_nav(50000.0, 50000.0, 10000.0, 0.0, 1000.0)
    assert nav_high_cost < nav_low_cost
