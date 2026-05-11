# Data README

Главный файл для backtest:

```text
data/processed/market_data.csv
```

## Columns

| Column | Type | Description |
|---|---|---|
| `timestamp` | datetime UTC | observation timestamp |
| `eth_price_usdc` | float | ETH price in USDC/USD proxy |
| `uni_tvl_usd` | float | Uniswap V2 WETH/USDC pool TVL |
| `uni_volume_usd` | float | pool volume over period |
| `uni_fees_usd` | float | `uni_volume_usd × 0.003` |
| `uni_liquidity` | float | Uniswap V2 LP token supply / liquidity proxy |
| `aave_weth_borrow_rate` | float | WETH borrow rate per period |
| `aave_usdc_supply_rate` | float | USDC supply rate per period |
| `gas_cost_usdc` | float | assumed gas cost per rebalance |
| `regime` | string | market regime label |

## Sources

- ETH price: CoinGecko ETH/USD, used as ETH/USDC proxy.
- Uniswap V2 WETH/USDC: The Graph / Uniswap V2 subgraph.
- Aave rates: Aave V3 GraphQL API.
- Fees: `volume × 0.30%`.

## Frequency

Preferred: hourly.

Fallback: daily.

If hourly data is incomplete, the final whitepaper should explicitly mention the fallback to daily data.
