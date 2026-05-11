import math


def test_target_weth_debt():
    lp_eth_delta = 10.0
    hedge_ratio = 0.75
    expected = 7.5
    result = hedge_ratio * lp_eth_delta
    assert result == expected


def test_hedge_error():
    target_weth_debt = 7.5
    current_weth_debt = 6.0
    lp_eth_delta = 10.0
    hedge_error = abs(target_weth_debt - current_weth_debt) / lp_eth_delta
    assert math.isclose(hedge_error, 0.15)


def test_idle_value():
    idle_usdc = 1000.0
    idle_weth = 0.5
    eth_price = 2000.0
    idle_value = idle_usdc + idle_weth * eth_price
    assert idle_value == 2000.0


def test_idle_ratio():
    idle_value = 2000.0
    nav = 100000.0
    idle_ratio = idle_value / nav
    assert math.isclose(idle_ratio, 0.02)


def test_aave_debt_value():
    borrowed_weth = 5.0
    eth_price = 2000.0
    debt_value = borrowed_weth * eth_price
    assert debt_value == 10000.0


def test_ltv():
    debt_value = 10000.0
    collateral_value = 50000.0
    ltv = debt_value / collateral_value
    assert math.isclose(ltv, 0.20)


def test_health_factor():
    collateral_value = 50000.0
    liquidation_threshold = 0.80
    debt_value = 10000.0
    health_factor = collateral_value * liquidation_threshold / debt_value
    assert math.isclose(health_factor, 4.0)
