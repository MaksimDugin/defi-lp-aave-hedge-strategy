# Описание данных

| Данные | Источник | Частота | Зачем нужны |
|---|---|---|---|
| ETH/USDC price | Uniswap V2 / внешний price source | hourly или daily | оценка LP-позиции и hedge debt |
| Uniswap V2 TVL | The Graph / `fractal-defi` loader | hourly или daily | оценка стоимости LP-позиции |
| Uniswap V2 volume | The Graph / `fractal-defi` loader | hourly или daily | расчёт комиссионного дохода LP |
| Uniswap V2 fees | `volume × 0.30%` | hourly или daily | доходность LP от комиссий |
| Aave V3 WETH borrow APY | Aave V3 / `fractal-defi` loader | hourly или daily | стоимость funding для hedge |
| Aave V3 USDC supply APY | Aave V3 / `fractal-defi` loader | hourly или daily | доходность collateral |
| Gas cost | fixed scenario или историческая оценка | на каждую ребалансировку | execution cost |
| Slippage | фиксированная bps-модель или volume-based estimate | на каждую сделку | execution cost |

## Основные допущения

- USDC используется как accounting currency.
- Borrowed WETH считается short ETH exposure.
- Комиссия Uniswap V2 принимается равной 0.30%.
- Если hourly data недоступны или нестабильны, используется daily frequency.
- Все данные синхронизируются по timestamp.
- Пропуски удаляются или заполняются только явно описанным способом.
