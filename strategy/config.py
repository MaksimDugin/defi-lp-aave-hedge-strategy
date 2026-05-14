
@dataclass
class StrategyConfig:
    initial_capital_usdc: float = 100_000.0
    lp_allocation: float = 0.50
    aave_collateral_allocation: float = 0.50
    hedge_ratio: float = 0.75
    rebalance_threshold: float = 0.10
    max_ltv: float = 0.50
    liquidation_threshold: float = 0.80
    min_health_factor: float = 1.50
    emergency_health_factor: float = 1.25
    slippage_bps: float = 10.0
    gas_cost_usdc: float = 15.0
    idle_ratio_limit: float = 0.05