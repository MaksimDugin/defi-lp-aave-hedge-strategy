from dataclasses import dataclass
import pandas as pd


@dataclass
class PortfolioState:
    timestamp: pd.Timestamp

    cash_usdc: float

    lp_tokens: float
    lp_share: float
    lp_value_usdc: float

    weth_debt: float
    weth_debt_usdc: float

    collateral_usdc: float

    equity_usdc: float

    realized_pnl_usdc: float
    unrealized_pnl_usdc: float

    fees_collected_usdc: float
    funding_paid_usdc: float
    gas_paid_usdc: float