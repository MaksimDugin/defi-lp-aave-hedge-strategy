

def calculate_target_weth_debt(
         lp_eth_delta: float,
        hedge_ratio: float,
    ):
    return lp_eth_delta * hedge_ratio


def calculate_hedge_error(
    current_weth_debt: float,
    target_weth_debt: float,
) -> float:
    
    error = abs(current_weth_debt - target_weth_debt) / target_weth_debt

    return error
    

def should_rebalance(
        hedge_error: float,
        rebalance_threshold: float,
) -> bool:
    return hedge_error >= rebalance_threshold


def calculate_idle_value(
        idle_usdc: float,
        idle_weth: float,
        eth_price: float,
) -> float:
    idle_value = idle_usdc + idle_weth * eth_price
    return idle_value


def calculate_idle_ratio(
        idle_value: float,
        nav: float,
) -> float:
    idle_ratio = idle_value/ nav
    return idle_ratio


def calculate_debt_value(
        borrowed_weth: float,
        eth_price: float,
) -> float:
    debt_value = borrowed_weth * eth_price
    return debt_value


def calculate_ltv(
        debt_value: float,
        collateral_value: float,
) -> float:
    ltv = debt_value / collateral_value
    return ltv


def calculate_health_factor(
        collateral_value: float,
        liquidation_threshold: float,
        debt_value: float,
) -> float:

    health_factor = collateral_value * liquidation_threshold / debt_value

    return health_factor


def calculate_nav(
        lp_value,
        collateral_value,
        idle_value ,
        debt_value
) -> float:
    nav = lp_value + collateral_value + idle_value - debt_value
    return nav