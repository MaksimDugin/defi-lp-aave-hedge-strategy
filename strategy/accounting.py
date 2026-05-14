

def calculate_target_weth_debt(
         lp_eth_delta: float,
        hedge_ratio: float,
    ):
    return lp_eth_delta * hedge_ratio


def calculate_hedge_error(
    current_weth_debt: float,
    target_weth_debt: float,
) -> float:
    if target_weth_debt > 0:
        error = abs(current_weth_debt - target_weth_debt) / target_weth_debt
    else: 
        raise ValueError("Target weth debt is not positive! Are you sure everything is right?"); 
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
    if nav > 0:
        idle_ratio = idle_value/ nav
    else: 
        raise ValueError("NAV is not positive! Are you sure everything is right?"); 
    
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
    
    if collateral_value > 0:
        ltv = debt_value / collateral_value
    else: 
        raise ValueError("Collateral_value is not positive! Are you sure everything is right?")
    
    return ltv


def calculate_health_factor(
        collateral_value: float,
        liquidation_threshold: float,
        debt_value: float,
) -> float:
    
    if debt_value > 0:
        health_factor = collateral_value * liquidation_threshold / debt_value
    else:
        raise ValueError("Debt value is not positive! Are you sure everything is right?")
    return health_factor


def calculate_nav(
        lp_value,
        collateral_value,
        idle_value ,
        debt_value
) -> float:
    nav = lp_value + collateral_value + idle_value - debt_value
    return nav