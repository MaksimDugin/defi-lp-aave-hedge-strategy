# Aave-хеджированная LP-стратегия ETH/USDC

## 1. Аннотация

В проекте реализуется и тестируется консервативная DeFi-стратегия предоставления ликвидности в Uniswap V2 ETH/USDC с частичным хеджированием через Aave V3. Стратегия делит капитал между LP-позицией и collateral reserve, занимает WETH в Aave V3 и использует этот заём как short ETH exposure для снижения направленного риска LP-позиции.

Стратегия сравнивается с buy & hold 50/50 ETH/USDC, plain Uniswap V2 LP и LP с fixed initial hedge. Проверка проводится на исторических данных и через Monte Carlo stress tests для разных рыночных режимов.

Главная исследовательская гипотеза: частичное хеджирование ETH exposure через Aave V3 может улучшить результат plain Uniswap V2 LP, сохранив доход от AMM-комиссий и снизив направленный риск ETH.

---

## 2. Постановка проблемы

Поставщики ликвидности в Uniswap V2 получают комиссионный доход от сделок в пуле, но одновременно несут риск impermanent loss. Для ETH/USDC LP-позиция ведёт себя как автоматически ребалансируемый портфель: при росте ETH пул продаёт ETH, а при падении ETH покупает ETH. Из-за этого LP-позиция имеет отрицательную gamma exposure и может проигрывать простой стратегии buy & hold при сильном направленном движении цены.

Цель проекта — проверить, может ли частичный hedge через Aave V3 улучшить результат plain Uniswap V2 LP. Для этого стратегия занимает WETH под USDC collateral и использует borrowed WETH как short ETH exposure против ETH-delta LP-позиции.

Основной источник потенциальной доходности стратегии — AMM fee income. Основные источники риска и издержек — impermanent loss, funding cost по WETH borrow, gas, slippage, liquidation risk и ошибки ребалансировки.

---

## 3. Гипотеза стратегии

Основная гипотеза состоит в том, что частичное хеджирование ETH exposure через Aave V3 может улучшить результат plain Uniswap V2 LP, сохранив доход от AMM-комиссий и снизив направленный риск ETH.

Ожидается, что стратегия будет лучше работать в боковых и умеренно волатильных режимах, где комиссионный доход LP способен компенсировать Aave borrow cost, gas costs и slippage. В сильном тренде стратегия может уступать buy & hold и даже plain LP из-за стоимости хеджа и отрицательной gamma LP-позиции.

Гипотеза не предполагает, что стратегия создаёт безрисковую доходность. Проект проверяет trade-off между LP fee income и hedge costs.

---

## 4. Инструменты стратегии

В проекте используются следующие инструменты:

- Uniswap V2 ETH/USDC pool — площадка для предоставления ликвидности;
- Aave V3 — протокол lending/borrowing для открытия hedge;
- USDC — accounting currency и collateral asset;
- WETH — borrowed asset, используемый для short ETH exposure;
- `fractal-defi` — библиотека для реализации воспроизводимого backtest;
- Forge / Solidity — слой vault-прототипа и тестирования on-chain logic.

---

## 5. Связь с предыдущими проектами

Финальный проект развивает идеи предыдущих работ. В Solidity vault prototype уже была реализована базовая логика Uniswap V2 LP + Aave hedge: расчёт LP delta, `rebalance()`, health factor, LTV constraints и circuit breaker. В предыдущем ДЗ по Uniswap V3 была протестирована идея LP-стратегии с хеджированием и анализом рыночных режимов.

В финальном проекте эти идеи переносятся в воспроизводимый research-backtest на исторических данных. Основной фокус смещается с архитектуры vault на проверку экономической гипотезы: может ли Aave-хедж улучшить plain Uniswap V2 LP после учёта funding, gas, slippage и риска ребалансировки.

Uniswap V2 выбран вместо Uniswap V3, потому что full-range LP exposure проще формализовать, проще объяснить через constant product AMM и легче защитить в mini whitepaper. Uniswap V3 concentrated liquidity остаётся важным направлением для будущего улучшения, но в рамках этого проекта она создала бы дополнительные допущения по выбору диапазона и управлению активной ликвидностью.

---

## 6. Implementation structure

Проект состоит из двух уровней реализации.

### 6.1. Vault prototype: Forge / Solidity

Solidity-часть показывает, как стратегия может быть реализована как DeFi vault. Она включает deposit, withdraw, rebalance, health factor checks, LTV limits, slippage limits и circuit breaker. Эта часть нужна для проверки архитектуры стратегии и её on-chain feasibility.

Forge-тесты проверяют:

- deposit / withdraw logic;
- корректность `rebalance()`;
- ограничения по LTV и health factor;
- работу circuit breaker;
- pause / unpause;
- slippage limits;
- базовое capital accounting.


### 6.1.1. Sepolia prototype deployment

Solidity-прототип был дополнительно задеплоен в Sepolia как mock-based demo environment. Деплой включает mock USDC, mock WETH, mock Uniswap V2 Router/Pair, mock Chainlink ETH/USD oracle, mock Aave Pool и сам `ImpermanentLossHedgingVault`.

Deployment addresses:

| Contract | Address |
|---|---|
| Deployer | `0x105a2357d6e6614810296020eBB551Dda6EfaFd9` |
| MockERC20 / mUSDC | `0x9524e79b9199f6C3777e372db8B4cF0d28Bc3dFa` |
| MockWETH9 | `0xBDA327305ac766Ef56A6621575f059164D9CD76b` |
| MockUniswapV2Router02 | `0x43a915c119a0C5e3a1f0E047a6ce646e3627a51a` |
| MockUniswapV2Pair | `0x1BD44Ff5eAa4402Db5D7efeb91634f377D352416` |
| MockOracle | `0x9B2752d78A4A9538d4769fc69cC9D77E9AD5Cd7e` |
| MockAavePool | `0x4A3D8DFA4F691c5a11F1910FFa603646B8DD29c7` |
| ImpermanentLossHedgingVault | `0xE7BD0aCe788298b8b35e13CC931230EA28028603` |

Smoke-test transaction:

```text
Deposit tx: 0xfc4c56193cf3feabcd30a1661dd2a6433126a16ccb24dd5aa79c8d980f3efbc9
```

Smoke-test parameters:

```text
deposit ETH amount = 0.005 ETH
deposit USDC amount = 10 mUSDC
pool price = 2000 USDC / ETH
```

Post-deposit checks:

```text
totalShares = 5e15
getCurrentDelta = 5e15
getCurrentDebt ≈ 5e15
getHealthFactorBps = 16000
getCapitalPosition1e18:
    lpAssetValue = 20e18
    debtValue = 10e18
    netAssetValue = 10e18
```

Этот smoke test подтверждает, что vault принимает deposit, создаёт LP-like shares, открывает WETH debt hedge через mock Aave Pool и корректно считает базовые accounting/risk values.

### 6.2. Research backtest: Python / fractal-defi

Python-часть используется для исторического backtest и Monte Carlo stress tests. Она реализует экономическую модель стратегии, сравнивает её с baseline-стратегиями и считает метрики: net PnL, annualized return, Sharpe, max drawdown, turnover, fees, funding costs, gas и slippage.

Такое разделение позволяет отдельно проверить техническую реализуемость vault и экономическую эффективность стратегии.

---

## 7. Формальное описание стратегии

### 7.1. Общая идея

Стратегия строится вокруг LP-позиции в Uniswap V2 ETH/USDC и частичного хеджирования её ETH exposure через Aave V3. LP-позиция зарабатывает комиссии от торгового объёма в пуле, но несёт риск impermanent loss и направленный риск ETH. Чтобы снизить этот риск, стратегия занимает WETH в Aave V3 под USDC collateral и использует этот заём как short ETH exposure.

Начальный капитал делится на две части:

- 50% капитала направляется в Uniswap V2 ETH/USDC LP;
- 50% капитала используется как collateral / hedge reserve в Aave V3.

Borrowed WETH считается реальным short ETH: предполагается, что после займа WETH продаётся в USDC. Это позволяет компенсировать часть ETH exposure LP-позиции.

### 7.2. LP-позиция в Uniswap V2

Uniswap V2 использует constant product AMM:

$$
x_t y_t = k_t,
$$

где:

- $x_t$ — количество ETH в пуле;
- $y_t$ — количество USDC в пуле;
- $k_t$ — constant product;
- $P_t$ — цена ETH в USDC.

Для симметричной LP-позиции стоимость позиции можно приближённо записать как:

$$
V_{LP,t} = 2L\sqrt{P_t},
$$

где $L$ — параметр ликвидности, связанный с размером позиции.

ETH-delta LP-позиции определяется как производная стоимости LP по цене ETH:

$$
\Delta_{LP,t} = \frac{\partial V_{LP,t}}{\partial P_t}
= \frac{L}{\sqrt{P_t}}.
$$

На практике для Uniswap V2 эту дельту можно интерпретировать проще: она примерно равна количеству ETH, которое находится внутри LP-позиции стратегии в данный момент времени.

### 7.3. Target hedge

Стратегия не использует полный hedge, потому что полный delta hedge может быть слишком дорогим из-за Aave borrow cost, gas costs, slippage и частых ребалансировок. Поэтому используется частичный hedge.

Целевой размер WETH debt определяется как:

$$
D^{target}_{WETH,t} = h \cdot \Delta_{LP,t},
$$

где:

- $D^{target}_{WETH,t}$ — целевой объём borrowed WETH;
- $h$ — hedge ratio;
- $\Delta_{LP,t}$ — ETH-delta LP-позиции.

Базовое значение:

$$
h = 0.75.
$$

Для sensitivity analysis дополнительно рассматривается $h = 0.50.$

### 7.4. Rebalance rule

На каждом timestamp стратегия сравнивает текущий объём WETH debt с целевым.

Hedge error считается как:

$$
HE_t =
\frac{
|D^{target}_{WETH,t} - D^{current}_{WETH,t}|
}{
\Delta_{LP,t}
}.
$$

Если hedge error превышает заданный threshold, стратегия выполняет rebalance:

$$
HE_t > \theta.
$$

Базовое значение threshold:

$$
\theta = 10\%.
$$

Если текущий WETH debt ниже целевого, стратегия занимает дополнительный WETH через Aave V3 и продаёт его в USDC. Если текущий WETH debt выше целевого, стратегия покупает WETH за USDC и погашает часть долга.

### 7.5. NAV стратегии

Стоимость стратегии считается в USDC. Полный NAV включает LP-позицию, Aave collateral, Aave debt, idle tokens и накопленные costs:

$$
NAV_t = V_{LP,t} + C_{Aave,t} - D_{Aave,t} + Idle_t - Costs_t.
$$

Где:

- $V_{LP,t}$ — стоимость LP-позиции;
- $C_{Aave,t}$ — стоимость collateral в Aave;
- $D_{Aave,t}$ — стоимость borrowed WETH debt;
- $Idle_t$ — стоимость неиспользуемых активов;
- $Costs_t$ — накопленные gas, slippage и transaction costs.

Idle tokens учитываются отдельно, чтобы избежать скрытой неэффективности капитала. Idle value считается как:

$$
Idle_t = IdleUSDC_t + IdleWETH_t \cdot P_t.
$$

Idle ratio:

$$
IdleRatio_t = \frac{Idle_t}{NAV_t}.
$$

Если idle ratio становится слишком высоким, стратегия считается менее capital-efficient.

### 7.6. PnL decomposition

Итоговый PnL стратегии раскладывается на несколько компонентов:

$$
NetPnL = LPFees - ImpermanentLoss - AaveBorrowCost + AaveSupplyYield - GasCosts - SlippageCosts.
$$

Основной источник доходности стратегии — комиссии Uniswap V2. Основные источники потерь — impermanent loss, стоимость займа WETH в Aave, gas costs, slippage и издержки ребалансировки.

Таким образом, стратегия может быть успешной только если доход от AMM-комиссий и эффект снижения directional exposure превышают стоимость hedge и execution costs.

### 7.7. Risk constraints

Стратегия использует несколько ограничений риска:

1. **LTV limit** — стратегия не должна превышать максимальный loan-to-value в Aave.
2. **Minimum health factor** — если health factor приближается к опасному уровню, стратегия не увеличивает debt и может частично погасить WETH debt.
3. **Circuit breaker** — при резких движениях цены, падении ликвидности, росте borrow APY или ухудшении health factor стратегия приостанавливает увеличение hedge.
4. **Gas-aware rebalance** — rebalance выполняется только если ожидаемая польза от корректировки hedge превышает execution costs.
5. **Idle token accounting** — все неиспользуемые токены включаются в NAV и отдельно отслеживаются через idle ratio.

---

## 8. Pseudocode

```text
Input:
    initial_capital_USDC
    hedge_ratio
    rebalance_threshold
    min_health_factor
    max_ltv
    gas_cost_per_rebalance
    slippage_bps

Initialize:
    accounting_currency = USDC

    lp_capital = 50% of initial_capital_USDC
    aave_capital = 50% of initial_capital_USDC

    Convert half of lp_capital to ETH
    Add ETH and USDC liquidity to Uniswap V2 ETH/USDC

    Deposit aave_capital as USDC collateral to Aave V3

    Calculate initial LP ETH delta
    target_weth_debt = hedge_ratio * LP_ETH_delta

    Borrow target_weth_debt WETH from Aave V3
    Sell borrowed WETH to USDC
    Record initial NAV

For each timestamp t:

    Update ETH/USDC price
    Update Uniswap V2 pool state
    Update Aave/funding rates

    Accrue Uniswap LP fees
    Accrue Aave borrow cost
    Accrue Aave supply yield

    Calculate:
        LP_value_t
        LP_ETH_delta_t
        current_weth_debt_t
        target_weth_debt_t = hedge_ratio * LP_ETH_delta_t
        hedge_error_t
        health_factor_t
        idle_tokens_t
        NAV_t

    Check circuit breaker:

        If ETH price jump is too large:
            circuit_breaker = True

        If pool liquidity is too low:
            circuit_breaker = True

        If Aave health factor is too low:
            circuit_breaker = True

        If Aave WETH borrow APY spikes:
            circuit_breaker = True

    If circuit_breaker is True:

        Do not increase WETH debt

        If health_factor_t is below safety threshold:
            Buy WETH
            Repay part of Aave debt
            Apply gas and slippage costs

        Record circuit breaker event
        Record NAV
        Continue to next timestamp

    Else:

        If hedge_error_t > rebalance_threshold:

            If target_weth_debt_t > current_weth_debt_t:

                additional_debt = target_weth_debt_t - current_weth_debt_t

                Check max LTV
                Check minimum health factor
                Check expected gas and slippage costs

                If risk checks pass:
                    Borrow additional_debt WETH from Aave
                    Sell borrowed WETH to USDC
                    Apply gas and slippage costs
                    Record turnover

            Else if target_weth_debt_t < current_weth_debt_t:

                repay_amount = current_weth_debt_t - target_weth_debt_t

                Buy repay_amount WETH using USDC
                Repay WETH debt on Aave
                Apply gas and slippage costs
                Record turnover

        Else:
            Do nothing

    Record:
        timestamp
        ETH price
        LP value
        Aave collateral
        Aave debt
        idle tokens
        NAV
        LP fees
        Aave borrow cost
        Aave supply yield
        gas costs
        slippage costs
        health factor
        hedge error
        turnover
        rebalance event

At the end of the backtest:

    Close LP position
    Buy WETH needed to repay remaining Aave debt
    Repay Aave debt
    Withdraw collateral
    Convert final portfolio value to USDC

Calculate final metrics:

    Net PnL
    Annualized return
    Annualized volatility
    Sharpe ratio
    Max drawdown
    Turnover
    Number of rebalances
    Total LP fees
    Total Aave borrow cost
    Total gas costs
    Total slippage costs
    Average health factor
    Average idle ratio

Compare with baselines:
    Buy & Hold 50/50 ETH/USDC
    Plain Uniswap V2 ETH/USDC LP
    LP with fixed initial hedge
```

---

## 9. Data description

### 9.1. Итоговый датасет

Итоговый датасет содержит 8737 hourly-наблюдений за период с 2025-01-01 00:00 UTC по 2025-12-31 00:00 UTC. В датасете нет пропусков и дубликатов timestamp, а все временные ряды синхронизированы по hourly frequency.

Основной файл для backtest:

```text
data/processed/market_data.csv
```

Он содержит следующие поля:

- `timestamp` — время наблюдения;
- `eth_price_usdc` — цена ETH в USDC;
- `uni_tvl_usd` — TVL Uniswap V2 WETH/USDC pool;
- `uni_volume_usd` — hourly trading volume пула;
- `uni_fees_usd` — estimated pool fees, рассчитанные как `volume × 0.003`;
- `uni_liquidity` — total LP supply / liquidity measure;
- `aave_weth_borrow_rate` — per-period funding cost proxy для WETH borrow;
- `aave_usdc_supply_rate` — per-period yield proxy для USDC collateral;
- `gas_cost_usdc` — fixed gas cost assumption;
- `regime` — рыночный режим для ex-post анализа результатов.

Цена ETH/USDC берётся из Binance ETHUSDC historical data. Данные по Uniswap V2 WETH/USDC pool получены через The Graph. Aave funding представлен через SOFR-based proxy, поскольку исторические Aave reserve-specific rates не удалось стабильно получить из публичных источников.


### 9.1.1. Финальная реализация backtest через fractal-defi

Финальная версия historical backtest запускается через модуль:

```bash
python -m strategy.fractal_runner \
  --data-path data/processed/market_data.csv \
  --output-dir reports/results_tables
```

В этой версии `fractal-defi` используется как основной слой моделирования AMM LP-механики. Исторический `market_data.csv` преобразуется в последовательность `Observation`, где каждое наблюдение содержит `UniswapV2LPGlobalState`: цену ETH, TVL, объём торгов, комиссии и liquidity пула. LP-leg стратегий моделируется через `UniswapV2LPEntity`.

Aave-hedge layer реализован поверх fractal LP state: на каждом timestamp стратегия получает LP value и LP ETH delta из fractal-based LP-leg, затем рассчитывает target WETH debt, funding cost, health factor, hedge error, rebalance decision, gas, slippage и итоговый NAV.

Итоговые файлы backtest:

```text
reports/results_tables/nav_timeseries.csv
reports/results_tables/metrics.csv
reports/results_tables/rebalances.csv
reports/results_tables/pnl_decomposition.csv
```

Дополнительно после Optuna-калибровки был выполнен отдельный calibrated fractal-based backtest:

```bash
python -m strategy.fractal_runner \
  --data-path data/processed/market_data.csv \
  --output-dir reports/results_tables/fractal_calibrated \
  --hedge-ratio 0.8499892802109696 \
  --rebalance-threshold 0.06965934324744885 \
  --slippage-bps 10 \
  --gas-cost-usdc 15
  ```

Этот прогон используется как финальная calibrated specification dynamic Aave-hedged LP стратегии. Base specification сохраняется для сравнения и показывает результат исходной экономической гипотезы до калибровки.

Такой подход закрывает требование обязательного использования `fractal-defi`, но оставляет Aave accounting прозрачным и проверяемым, поскольку готовая Aave V3 lending/borrowing entity в используемой версии framework отсутствует.

### 9.2. Uniswap V2 data

Для Uniswap V2 WETH/USDC pool используются hourly TVL, trading volume, total liquidity и estimated fees. Комиссия Uniswap V2 принимается равной 0.30%, поэтому hourly pool fees рассчитываются как:

$$
Fees_t = Volume_t \times 0.003.
$$

Важно, что `uni_fees_usd` отражает комиссии всего пула, а не доход конкретной стратегии. В backtest стратегия получает только pro-rata долю комиссий:

$$
StrategyFees_t = PoolFees_t \times LPShare_t,
$$

где:

$$
LPShare_t = \frac{StrategyLiquidity_t}{PoolLiquidity_t}.
$$


### 9.3. Aave funding proxy

Для стратегии нужны две ставки:

- WETH borrow rate — стоимость займа WETH для hedge;
- USDC supply rate — доходность USDC collateral.

Исторические Aave WETH borrow и USDC supply rates не удалось стабильно получить через протестированные публичные источники. Official Aave GraphQL endpoint возвращал access errors, Aave subgraph не предоставлял стабильные historical rate queries для выбранного периода, а DeFiLlama Yields API был нестабилен в локальной среде.

Поэтому в основной версии dataset используется SOFR-based funding proxy. SOFR выбран как воспроизводимый внешний benchmark secured overnight funding rate. В базовой версии WETH borrow cost и USDC supply yield проксируются одним и тем же SOFR series.

Таким образом:

$$
AaveBorrowRate_t \approx SOFR_t,
$$

$$
AaveSupplyRate_t \approx SOFR_t.
$$

Ставки в итоговом датасете хранятся в per-period decimal формате. Для hourly backtest annualized rate переводится так:

$$
r^{hourly}_t = \frac{r^{annual}_t}{365 \times 24}.
$$

Это не является точной исторической Aave reserve-specific ставкой, но делает funding assumption прозрачным и воспроизводимым. Для проверки устойчивости результатов в дальнейшем используются sensitivity scenarios со spread над SOFR.

### 9.4. Data limitations

Основное ограничение связано с Aave rates. Исторические WETH borrow и USDC supply rates для Aave V3 не удалось стабильно получить из публичных источников за весь выбранный период. Поэтому в проекте используется SOFR-based funding proxy.

Это означает, что funding cost в backtest отражает не фактическую историю Aave WETH reserve utilization, а внешний воспроизводимый benchmark стоимости фондирования. Такой подход снижает точность моделирования Aave leg, но делает assumptions явными и позволяет провести sensitivity analysis.

Второе ограничение связано с Uniswap V2 liquidity. За рассматриваемый период TVL Uniswap V2 WETH/USDC pool снизился примерно на 53.6%, с 47.0 млн USD до 21.8 млн USD. Это указывает на liquidity migration risk: в реальном deployment часть ликвидности и торговой активности могла бы быть сосредоточена в Uniswap V3 или других DEX.

Третье ограничение связано с распределением торгового объёма. Volume и fee income имеют сильные выбросы: небольшое число stress-hours создаёт существенную часть pool fees. Поэтому результаты backtest могут быть чувствительны к отдельным high-volume observations. Для robustness желательно дополнительно протестировать стратегию на winsorized volume или без top 1% volume observations.

---

## 10. EDA summary

### 10.1. ETH market environment

За рассматриваемый период ETH снизился с 3357.20 USDC до 2963.59 USDC, то есть примерно на 11.7%. Минимальная цена составила 1417.45 USDC 2025-04-09, а максимальная — 4934.10 USDC 2025-08-24.

Annualized realized volatility ETH составила около 72.5%. Hourly returns варьировались от -11.6% до +9.6%, а распределение доходностей имеет выраженные fat tails: kurtosis около 17.2. Это подтверждает, что выбранный период содержит стрессовые движения и подходит для проверки LP-стратегии с хеджированием.

Для plain LP такая среда сложна: стратегия зарабатывает комиссии, но несёт impermanent loss и отрицательную gamma exposure. Для hedged LP этот период позволяет проверить, способен ли short WETH hedge снизить directional losses в периоды падения ETH.

### 10.2. Uniswap liquidity and fee opportunity

TVL Uniswap V2 WETH/USDC pool снизился с 47.0 млн USD до 21.8 млн USD, то есть примерно на 53.6%. Средний TVL составил около 31.3 млн USD, медианный — около 29.0 млн USD. Несмотря на снижение TVL, пул остаётся достаточно ликвидным для research-backtest.

Совокупный trading volume за период составил около 1.15 млрд USD. При fee rate 0.30% это соответствует примерно 3.45 млн USD estimated pool fees. Средние hourly fees составили около 394 USD, медианные — около 196 USD. Однако распределение fees сильно скошено: максимум hourly pool fees достигал 112.5 тыс. USD.

Это означает, что fee income LP-стратегии сильно зависит от отдельных high-volume periods. Для нашей стратегии это важно: hedge должен оцениваться не только по снижению directional exposure, но и по тому, не съедает ли rebalancing cost существенную часть fee income.

### 10.3. Funding proxy

SOFR-based funding proxy в среднем составил около 4.23% годовых, медианное значение — около 4.31%, максимум — около 4.51%. В базовой версии WETH borrow APY и USDC supply APY равны одному и тому же SOFR proxy, поэтому net funding spread равен нулю.

Это упрощающее допущение. В реальном Aave WETH borrow cost и USDC supply yield различались бы из-за reserve utilization, risk parameters и рыночного спроса на заём. Поэтому основной результат стратегии должен сопровождаться sensitivity analysis, например:

- base: WETH borrow = SOFR, USDC supply = SOFR;
- conservative: WETH borrow = SOFR + 2%, USDC supply = SOFR;
- stress: WETH borrow = SOFR + 5%, USDC supply = SOFR.

Такой подход позволяет проверить, насколько стратегия чувствительна к стоимости хеджа.

### 10.4. Regime analysis

Большая часть наблюдений относится к sideways regime — около 65.9% периода. High-volatility chop занимает около 18.0%, uptrend — около 8.2%, downtrend — около 7.7%. Warmup observations занимают менее 0.3%.

Анализ непрерывных regime segments показывает, что directional regimes обычно короткие. Downtrend имеет 106 сегментов со средней длиной около 6.3 часа и медианной длиной 2 часа. Uptrend имеет 121 сегмент со средней длиной около 5.9 часа и медианной длиной 2 часа. Sideways regime более устойчив: 209 сегментов со средней длиной около 27.6 часа и медианной длиной 9 часов.

Это поддерживает threshold-based rebalance rule. Если стратегия будет реагировать на каждое краткосрочное движение цены, transaction costs могут стать слишком высокими. Поэтому hedge должен ребалансироваться только при существенном отклонении от target debt.

### 10.5. Fee income by regime

Pool-level fees распределены неравномерно по рыночным режимам. Sideways regime даёт наибольшую сумму fees в абсолютном выражении — около 1.39 млн USD, что ожидаемо, потому что этот режим занимает большую часть периода.

Однако downtrend periods дают непропорционально высокий fee income: около 889 тыс. USD pool-level fees при всего 669 hourly observations. Это означает, что в stress/downtrend periods торговая активность резко возрастает. High-volatility chop также даёт значимую сумму fees — около 795 тыс. USD.

Для стратегии это важный вывод. Периоды стресса одновременно создают высокий fee income и высокий directional risk. Поэтому Aave hedge особенно важен именно в таких режимах: он может снизить убытки от падения ETH, пока LP-позиция получает повышенные комиссии.

### 10.6. Outlier analysis

В данных есть несколько экстремальных наблюдений по объёму, Volume/TVL и ETH returns. Самый высокий hourly volume был 2025-02-03 и составил около 37.5 млн USD, что соответствует примерно 112.5 тыс. USD pool fees. Этот же период совпадает с экстремальным движением ETH: самое сильное hourly падение составило около -11.6%.

Максимальный Volume/TVL ratio составил около 56.4% 2025-10-10. Это экстремальное значение, но оно совпадает с high-activity market event, а не выглядит как изолированный технический артефакт.

Эти observations не следует удалять из основного backtest, потому что именно такие периоды важны для LP-стратегии: они создают высокий fee income и одновременно проверяют устойчивость hedge logic. Однако для robustness полезно дополнительно протестировать стратегию на датасете с winsorized volume или без top 1% volume observations.

---

## 11. Calibration

Калибровка параметров проводится до финального сравнения стратегий. Базовые параметры выбираются из экономической логики стратегии, EDA и ограничений risk management, а затем проверяются через sensitivity analysis и Optuna calibration.

Базовые параметры:

```text
Initial capital = 100,000 USDC
LP allocation = 50%
Aave collateral allocation = 50%
base hedge_ratio = 75%
base rebalance_threshold = 10%
min_health_factor = 1.5
idle_ratio_limit = 5%
slippage_bps = 10
base gas cost = 15 USDC per rebalance
```

В проекте используется более консервативный подход с разделением параметров:

```text
1. EDA / data-driven assumptions:
   - max_price_jump
   - gas_cost_usdc
   - slippage_bps
   - funding proxy

2. Risk policy / protocol constraints:
   - min_health_factor
   - max_ltv
   - liquidation_threshold

3. Strategy-control parameters:
   - hedge_ratio
   - rebalance_threshold
```

Оптимизация применяется только к strategy-control параметрам. Gas, slippage, LTV, health factor и funding assumptions не подбираются для максимизации historical PnL, потому что они отражают условия исполнения и risk policy.

### 11.1. Использование EDA для ограничения calibration space

EDA использовалась не только для описания данных, но и для выбора реалистичных границ параметров.

Во-первых, hourly ETH returns имеют тяжёлые хвосты: минимальное hourly movement около -11.6%, максимальное около +9.6%. Поэтому circuit breaker threshold должен быть достаточно высоким, чтобы не срабатывать на обычный шум, но достаточно низким, чтобы блокировать увеличение debt во время stress move. Базовое значение `max_price_jump = 10%` связано с этой частью EDA.

Во-вторых, regime analysis показал, что directional regimes часто короткие: медианная длина uptrend/downtrend segments около 2 часов. Это означает, что слишком частый rebalance будет реагировать на шум и создавать издержки. Поэтому `rebalance_threshold` калибруется в умеренном диапазоне, а не близко к нулю.

В-третьих, fee income сильно сконцентрирован в high-volume stress periods. Это поддерживает саму идею hedge: именно в периоды высокого объёма стратегия получает комиссии, но одновременно сталкивается с высоким directional risk.

### 11.2. Continuous Optuna calibration

После grid/sensitivity проверки была проведена continuous calibration через Optuna. Оптимизировались два параметра:

```text
hedge_ratio ∈ [0.40, 1.00]
rebalance_threshold ∈ [0.05, 0.20]
```

Objective function максимизировала risk-adjusted score. Score учитывает:

```text
- Sharpe ratio dynamic strategy;
- annualized return;
- max drawdown penalty;
- turnover penalty;
- transaction costs penalty;
- штраф за отсутствие dynamic behaviour, если number_of_rebalances = 0.
```

Цель такой calibration — не подобрать параметры, которые максимизируют только final NAV, а найти версию dynamic hedge с хорошим балансом между доходностью, downside protection и execution costs.

Всего было выполнено 800 Optuna trials. Лучший trial:

```text
Best trial = 361
Best value = 0.631080
hedge_ratio = 0.849989
rebalance_threshold = 0.069659
```

Top-10 trials оказались устойчиво сконцентрированы около:

```text
hedge_ratio ≈ 0.85
rebalance_threshold ≈ 6.9%–7.0%
number_of_rebalances = 13
```

| Trial | Score | Hedge ratio | Rebalance threshold | Final NAV | Sharpe | Max DD | Turnover | Rebalances | Total costs |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 361 | 0.631080 | 0.849989 | 0.069659 | 103,761.01 | 0.6328 | -2.04% | 22,182.97 | 13 | 217.18 |
| 624 | 0.631078 | 0.849982 | 0.069439 | 103,761.01 | 0.6328 | -2.04% | 22,182.79 | 13 | 217.18 |
| 352 | 0.631071 | 0.849958 | 0.069487 | 103,761.03 | 0.6328 | -2.04% | 22,182.15 | 13 | 217.18 |
| 245 | 0.631062 | 0.849927 | 0.069724 | 103,761.04 | 0.6327 | -2.05% | 22,181.35 | 13 | 217.18 |
| 495 | 0.630973 | 0.849623 | 0.069518 | 103,761.19 | 0.6327 | -2.05% | 22,173.40 | 13 | 217.17 |
| 242 | 0.630946 | 0.849531 | 0.069574 | 103,761.23 | 0.6326 | -2.05% | 22,171.01 | 13 | 217.17 |
| 183 | 0.630777 | 0.848960 | 0.069554 | 103,761.50 | 0.6324 | -2.06% | 22,156.11 | 13 | 217.16 |
| 440 | 0.630158 | 0.849997 | 0.069973 | 103,753.85 | 0.6319 | -2.05% | 22,175.76 | 13 | 217.18 |
| 174 | 0.630121 | 0.849868 | 0.069735 | 103,753.92 | 0.6318 | -2.05% | 22,172.40 | 13 | 217.17 |
| 80 | 0.630120 | 0.849864 | 0.069741 | 103,753.92 | 0.6318 | -2.05% | 22,172.31 | 13 | 217.17 |

Calibration plots сохраняются в:

```text
reports/figures/calibration_trials_scatter.png
reports/figures/calibration_heatmap_sharpe.png
reports/figures/calibration_heatmap_drawdown.png
```

### 11.3. Calibration result interpretation

Калибровка сместила параметры относительно базовой версии:

```text
Base strategy:
hedge_ratio = 0.75
rebalance_threshold = 10%

Calibrated strategy:
hedge_ratio ≈ 0.85
rebalance_threshold ≈ 7%
```
---

## 12. Baseline comparison

Для оценки качества стратегии используются три baseline. Это необходимо, чтобы отделить эффект LP-комиссий, эффект хеджирования и эффект динамической ребалансировки.

### 12.1. Baseline 1: Buy & Hold 50/50 ETH/USDC

Первый baseline — простая стратегия buy & hold. Начальный капитал делится между ETH и USDC в пропорции 50/50. После этого портфель не ребалансируется и не использует DeFi-протоколы.

Стоимость портфеля в момент времени $t$:

$$
V^{BH}_t = q_{ETH,0} \cdot P_t + q_{USDC,0},
$$

где:

- $q_{ETH,0}$ — начальное количество ETH;
- $q_{USDC,0}$ — начальное количество USDC;
- $P_t$ — цена ETH в USDC.

Этот baseline показывает, как стратегия выглядит по сравнению с простой пассивной экспозицией к ETH/USDC без impermanent loss, funding costs и transaction costs.

### 12.2. Baseline 2: Plain Uniswap V2 ETH/USDC LP

Второй baseline — обычная LP-позиция в Uniswap V2 ETH/USDC без хеджирования. Стратегия вносит ликвидность в пул и держит LP-позицию до конца периода.

Стоимость plain LP:

$$
V^{LP}_t = LPValue_t + LPFees_t - EntryExitCosts_t.
$$

Plain LP получает комиссионный доход, но несёт impermanent loss. Этот baseline является главным для проекта, потому что наша стратегия является модификацией обычной LP-стратегии.

Основной вопрос сравнения:

$$
V^{HedgedLP}_t > V^{PlainLP}_t?
$$

Иначе говоря, проверяется, способен ли Aave hedge улучшить результат обычного LP после учёта funding, gas, slippage и ребалансировок.

### 12.3. Baseline 3: LP with fixed initial hedge

Третий baseline — LP-позиция с фиксированным начальным hedge. В начале периода стратегия открывает LP-позицию, рассчитывает начальную ETH-delta и занимает WETH через Aave V3. После этого hedge не ребалансируется.

Целевой начальный hedge:

$$
D^{fixed}_{WETH,0} = h \cdot \Delta_{LP,0}.
$$

Для всех последующих моментов времени:

$$
D^{fixed}_{WETH,t} = D^{fixed}_{WETH,0}.
$$

Этот baseline нужен, чтобы отделить эффект самого hedge от эффекта динамической ребалансировки. Если dynamic hedge показывает лучший результат, чем fixed hedge, значит ребалансировка добавляет ценность. Если fixed hedge оказывается не хуже, значит частая ребалансировка может быть экономически неоправданной из-за gas и slippage.

### 12.4. Main strategy: Dynamic Aave-hedged LP

Основная стратегия отличается от fixed hedge тем, что регулярно пересчитывает LP ETH-delta и корректирует WETH debt.

Целевой debt:

$$
D^{target}_{WETH,t} = h \cdot \Delta_{LP,t}.
$$

Rebalance выполняется только если:

$$
HE_t > \theta.
$$

При этом стратегия учитывает:

- Aave borrow cost;
- Aave collateral yield;
- gas costs;
- slippage;
- health factor;
- LTV;
- circuit breaker;
- idle tokens.

### 12.5. Критерии сравнения

Стратегии сравниваются не только по финальному PnL, но и по risk-adjusted metrics.

Основные метрики:

- final NAV;
- net PnL;
- annualized return;
- annualized volatility;
- Sharpe ratio;
- max drawdown;
- turnover;
- number of rebalances;
- total LP fees;
- total Aave borrow cost;
- total gas costs;
- total slippage costs;
- average health factor;
- average idle ratio.

Главная цель стратегии — показать улучшение относительно plain Uniswap V2 LP. Улучшение может проявляться в нескольких формах:

1. более высокий final NAV;
2. более высокий Sharpe ratio;
3. меньший max drawdown;
4. меньшая volatility;
5. лучшая устойчивость в отдельных рыночных режимах.

Финальный вывод строится не только на том, победила ли стратегия baseline по доходности, но и на том, насколько оправданным оказался trade-off между LP fee income и hedge costs.

---

## 13. Backtesting protocol

### 13.1. Цель backtest

Backtest нужен для проверки, улучшает ли Aave-хеджированная LP-стратегия результат plain Uniswap V2 ETH/USDC LP после учёта всех основных издержек:

- impermanent loss;
- Aave borrow cost;
- Aave supply yield;
- gas costs;
- slippage;
- rebalancing turnover;
- idle token inefficiency.

Главное сравнение проводится между:

1. Buy & Hold 50/50 ETH/USDC;
2. plain Uniswap V2 ETH/USDC LP;
3. LP с fixed initial hedge;
4. dynamic Aave-hedged LP.

Основной benchmark — plain Uniswap V2 LP, потому что наша стратегия является его модификацией.


### 13.1.1. Реализация backtest через fractal-defi

Финальный historical backtest реализован как fractal-based pipeline. Модуль `strategy/fractal_runner.py` выполняет следующие шаги:

1. Загружает `data/processed/market_data.csv`.
2. Преобразует строки датасета в `fractal-defi Observation`.
3. Для LP-механики использует `UniswapV2LPEntity` и `UniswapV2LPGlobalState`.
4. Запускает четыре стратегии:
   - `buy_hold_50_50`;
   - `fractal_plain_uniswap_v2_lp`;
   - `fractal_fixed_hedge_lp`;
   - `fractal_dynamic_aave_hedged_lp`.
5. Сохраняет `nav_timeseries.csv`, `metrics.csv`, `rebalances.csv` и `pnl_decomposition.csv`.

Ключевое разделение реализации:

```text
fractal-defi:
    AMM LP mechanics, LP value, LP state, LP observation flow

project strategy layer:
    Aave hedge accounting, WETH debt, funding, health factor,
    circuit breaker, rebalance rule, gas/slippage, NAV decomposition
```

Это делает backtest воспроизводимым через framework primitives и одновременно сохраняет явное описание Aave-hedge assumptions.

### 13.1.2. Analytical notebook

Результаты historical backtest дополнительно оформлены в notebook:

```text
research/notebooks/02_backtest_results.ipynb
```

Notebook содержит:

загрузку calibrated fractal outputs;
таблицу финальных метрик;
equity curve;
drawdown plot;
hedge diagnostics;
rebalance events;
PnL decomposition;
top calibration trials;
base vs calibrated dynamic comparison;
regime-level result summary.

Notebook используется как промежуточный слой между raw outputs и whitepaper: все численные выводы в разделе Results берутся из сохранённых .csv файлов, а графики и аналитические комментарии формируются воспроизводимо.

### 13.2. Начальные условия

Базовые параметры backtest:

```text
Initial capital = 100,000 USDC
Accounting currency = USDC
LP allocation = 50%
Aave collateral allocation = 50%
Pool = Uniswap V2 ETH/USDC
Lending protocol = Aave V3
Collateral asset = USDC
Borrowed asset = WETH
Base hedge ratio = 75%
Rebalance threshold = 10%
Minimum health factor = 1.5
Idle ratio limit = 5%
```

Начальный капитал делится на две равные части:

```text
50,000 USDC equivalent → Uniswap V2 ETH/USDC LP
50,000 USDC → Aave V3 collateral reserve
```

Для LP leg половина LP-капитала конвертируется в ETH, вторая половина остаётся в USDC. Затем ETH и USDC вносятся в Uniswap V2 ETH/USDC pool.

Для hedge leg USDC вносится в Aave V3 как collateral. После этого стратегия занимает WETH, продаёт borrowed WETH в USDC и учитывает эту позицию как short ETH exposure.

### 13.3. Частота backtest

Основная частота backtest — hourly. Hourly frequency предпочтительнее, потому что она лучше отражает:

- изменение цены ETH;
- накопление LP fees;
- изменение funding rates;
- необходимость ребалансировки hedge;
- execution costs.

Если hourly data по отдельным источникам оказываются неполными или нестабильными, используется daily fallback, и это явно фиксируется в Data limitations.

### 13.4. Execution assumptions

Backtest использует следующие execution assumptions:

1. Сделки исполняются по наблюдаемой цене на timestamp.
2. Slippage учитывается отдельно через фиксированную bps-модель.
3. Gas cost применяется к каждому действию, требующему транзакции: LP entry, LP exit, borrow, repay, swap borrowed WETH to USDC, swap USDC to WETH for repay, rebalance.
4. Aave borrow cost начисляется на outstanding WETH debt.
5. Aave supply yield начисляется на USDC collateral.
6. Rebalance происходит только при выполнении threshold condition и risk checks.
7. Circuit breaker может заблокировать увеличение debt.
8. Все idle tokens включаются в NAV.

### 13.5. Transaction costs

В backtest учитываются три типа execution costs.

#### Gas costs

Gas cost задаётся в USDC на каждую операцию:

```text
gas_cost_per_rebalance = fixed USDC amount
```

Для sensitivity analysis используются сценарии:

```text
gas_cost_per_rebalance ∈ {5, 15, 30} USDC
```

#### Slippage

Slippage задаётся как процент от notional сделки:

```text
slippage_cost = trade_notional × slippage_bps / 10,000
```

Базовый вариант:

```text
slippage_bps = 10
```

Для sensitivity analysis:

```text
slippage_bps ∈ {5, 10, 25}
```

#### Funding

Funding cost считается на outstanding WETH debt:

```text
borrow_cost_t = WETH_debt_t × ETH_price_t × borrow_rate_t
```

Supply yield считается на USDC collateral:

```text
supply_yield_t = USDC_collateral_t × supply_rate_t
```

### 13.6. Rebalancing assumptions

На каждом timestamp стратегия рассчитывает:

```text
target_weth_debt_t = hedge_ratio × LP_ETH_delta_t
```

Затем считается hedge error:

```text
hedge_error_t =
abs(target_weth_debt_t - current_weth_debt_t) / LP_ETH_delta_t
```

Rebalance выполняется, если:

```text
hedge_error_t > rebalance_threshold
```

Базовый threshold:

```text
rebalance_threshold = 10%
```

Если целевой debt выше текущего, стратегия занимает дополнительный WETH и продаёт его в USDC. Если целевой debt ниже текущего, стратегия покупает WETH за USDC и погашает часть Aave debt.

Rebalance не выполняется, если:

- circuit breaker активен;
- health factor ниже минимального уровня;
- LTV превышает лимит;
- ожидаемый эффект от rebalance меньше gas и slippage costs;
- данные на timestamp неполные.

### 13.7. Regime split

Результаты анализируются не только на всём периоде, но и по рыночным режимам.

Основные режимы:

```text
1. ETH uptrend
2. ETH downtrend
3. Sideways low-volatility market
4. High-volatility chop
5. Crash and recovery
```
Ожидается, что Aave hedge будет полезнее в боковом и волатильном рынке, где LP fees могут компенсировать funding и execution costs. В сильном направленном тренде hedge может ухудшать результат из-за стоимости займа и отрицательной gamma LP-позиции.

### 13.8. Backtesting implications from EDA

EDA задаёт несколько важных требований к реализации backtest.

Во-первых, `uni_fees_usd` отражает комиссии всего Uniswap V2 pool, поэтому стратегия должна получать только pro-rata долю fees в соответствии с её LP share.

Во-вторых, volume и fees имеют сильные выбросы. Основной backtest использует полный dataset, но robustness analysis должен проверять чувствительность результатов к top-volume observations.

В-третьих, directional regimes часто являются короткими. Поэтому режимы используются только для ex-post анализа результатов, а не как trading signal. Rebalance должен определяться hedge error threshold, risk checks и gas-aware condition.

В-четвёртых, в данных присутствуют экстремальные hourly ETH moves. Это делает circuit breaker обязательной частью стратегии. Circuit breaker должен блокировать увеличение debt при резком движении цены, ухудшении health factor или чрезмерных execution costs.

В-пятых, funding rates являются SOFR-based proxy. Поэтому backtest должен читать `aave_weth_borrow_rate` и `aave_usdc_supply_rate` из `market_data.csv`, а не hardcode'ить ставки внутри стратегии.

### 13.9. Monte Carlo stress tests

Помимо historical backtest, стратегия была дополнительно проверена на Monte Carlo stress scenarios. Цель Monte Carlo — не заменить historical data, а проверить, сохраняется ли основной вывод проекта в искусственно заданных рыночных режимах.

В Monte Carlo генерируются synthetic hourly paths для ETH price, Uniswap V2 TVL, volume, LP fees, Aave borrow/supply rates и gas costs. Затем каждый synthetic path прогоняется через тот же `fractal_runner`, что и historical backtest. Это важно: Monte Carlo использует ту же backtesting architecture, а не отдельную упрощённую модель стратегии.

Сценарии:

```text
1. strong_uptrend
2. strong_downtrend
3. sideways_low_vol
4. high_vol_chop
5. crash_recovery
```

Для каждого сценария сравниваются четыре стратегии:

- Buy & Hold 50/50
- Fractal Plain Uniswap V2 LP
- Fractal Fixed Hedge LP
- Fractal Dynamic Aave Hedged LP

Ключевые метрики:

- final NAV;
- median final NAV;
- 5% and 95% final NAV percentiles;
- max drawdown;
- annualized volatility;
- Sharpe ratio;
- number of rebalances;
- turnover;
- total costs;
- health factor;
- dynamic drawdown improvement vs plain LP.

Monte Carlo results используются как robustness check. Основной empirical result проекта остаётся historical fractal-based backtest, а Monte Carlo проверяет, насколько выводы устойчивы в synthetic stress regimes.

---

## 14. Risk management

### 14.1. Основные риски стратегии

Стратегия несёт несколько типов риска:

1. **Impermanent loss risk** — LP-позиция может проигрывать buy & hold при сильном изменении цены ETH.
2. **Funding risk** — стоимость займа WETH в Aave может оказаться выше дохода от LP fees.
3. **Liquidation risk** — если стоимость debt относительно collateral становится слишком высокой, Aave-позиция может приблизиться к liquidation threshold.
4. **Execution risk** — gas и slippage могут съесть выгоду от ребалансировки.
5. **Rebalance risk** — слишком частый rebalance увеличивает costs, слишком редкий rebalance оставляет большой directional exposure.
6. **Idle token risk** — часть капитала может лежать без работы и ухудшать capital efficiency.
7. **Liquidity risk** — при падении ликвидности в пуле сделки могут исполняться с высоким slippage.

### 14.2. Rebalance caller

В production-логике `rebalance()` должен вызываться внешним исполнителем.

Возможные варианты:

- собственный keeper bot;
- публичная keeper-инфраструктура;
- permissionless вызов функции любым пользователем;
- полуавтоматический manual rebalance.

В рамках backtest используется deterministic rebalance:

```text
На каждом timestamp стратегия проверяет условия rebalance.
Если threshold и risk checks выполнены, rebalance считается исполненным.
```

Это допущение явно отделяет backtest от production deployment. В production нужно дополнительно учитывать задержки исполнения, MEV, failed transactions и keeper incentives.

### 14.3. Circuit breaker

Circuit breaker нужен, чтобы стратегия не увеличивала debt в опасных рыночных условиях.

Circuit breaker активируется, если выполняется хотя бы одно условие:

```text
abs(ETH_return_t) > max_price_jump
pool_liquidity_t < min_liquidity
health_factor_t < min_health_factor
Aave_WETH_borrow_APY_t > max_borrow_apy
estimated_slippage_t > max_slippage
data_quality_flag_t = bad
```

Когда circuit breaker активен:

```text
- стратегия не увеличивает WETH debt;
- стратегия может частично погасить debt;
- новые LP entries не выполняются;
- событие записывается в backtest logs;
- NAV продолжает считаться с учётом текущих позиций.
```

EDA показывает наличие экстремальных hourly ETH returns: самое сильное падение составило около -11.6%, а самый сильный рост — около +9.6%. Такие движения могут резко изменить LP delta, стоимость Aave debt и health factor. Поэтому circuit breaker является обязательным элементом risk management.

### 14.4. LTV и health factor

Для Aave-позиции отслеживаются:

```text
LTV_t = DebtValue_t / CollateralValue_t
```

И health factor:

```text
HealthFactor_t =
CollateralValue_t × LiquidationThreshold / DebtValue_t
```

Базовое ограничение:

```text
min_health_factor = 1.5
```

Если health factor падает ниже заданного уровня, стратегия:

1. не увеличивает WETH debt;
2. может купить WETH и погасить часть debt;
3. записывает risk event;
4. может временно остановить rebalance.

### 14.5. Idle tokens

Idle tokens — это активы, которые находятся внутри стратегии, но не используются продуктивно.

В нашем проекте idle tokens могут быть:

- USDC, который не внесён в LP и не deposited в Aave;
- WETH, который остался после rebalance и не использован для repay;
- ETH/USDC leftovers после добавления ликвидности;
- USDC после продажи borrowed WETH, если он не используется как collateral или reserve.

Idle value считается как:

```text
Idle_t = IdleUSDC_t + IdleWETH_t × ETH_price_t
```

Idle ratio:

```text
IdleRatio_t = Idle_t / NAV_t
```

Базовое ограничение:

```text
idle_ratio_limit = 5%
```

Если idle ratio становится выше лимита, это означает, что стратегия использует капитал неэффективно. В результатах idle ratio показывается отдельно.

### 14.6. Gas-aware rebalance

Rebalance выполняется только если ожидаемая польза от корректировки hedge оправдывает transaction costs.

Условие:

```text
expected_rebalance_benefit > gas_cost + slippage_cost
```

Если hedge error превышает threshold, но notional ребалансировки слишком мал, стратегия может пропустить rebalance. Это защищает backtest от нереалистично частой торговли.

### 14.7. Slippage limits

Для каждой сделки считается slippage cost:

```text
slippage_cost = trade_notional × slippage_bps / 10,000
```

Если estimated slippage превышает допустимый лимит, стратегия не выполняет rebalance.

Это важно для реалистичности, потому что Aave hedge требует swap-операций:

- borrowed WETH → USDC;
- USDC → WETH для repay.

---

## 15. Results interpretation

### 15.1. Summary of results

В historical backtest сравниваются четыре типа стратегий:

1. Buy & Hold 50/50 ETH/USDC;
2. plain Uniswap V2 ETH/USDC LP;
3. LP with fixed initial hedge;
4. dynamic Aave-hedged LP.

Итоговая таблица historical backtest и calibrated run:

| Strategy | Final NAV | Net PnL | Ann. Return | Ann. Volatility | Sharpe | Max DD | Turnover | Rebalances | Total Costs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Buy & Hold 50/50 | 94,137.82 | -5,862.18 | -5.88% | 33.35% | -0.01 | -32.48% | 0.00 | 0 | 0.00 |
| Fractal Plain Uniswap V2 LP | 104,405.33 | 4,555.33 | 4.58% | 36.17% | 0.30 | -35.70% | 0.00 | 0 | 0.00 |
| Fractal Fixed Hedge LP | 105,835.60 | 5,910.60 | 5.93% | 7.72% | 0.79 | -5.57% | 0.00 | 0 | 0.00 |
| Base Dynamic Aave Hedge LP | 102,780.79 | 2,855.79 | 2.87% | 7.00% | 0.44 | -4.11% | 19,346.97 | 8 | 139.35 |
| Calibrated Dynamic Aave Hedge LP | 103,761.01 | 3,836.01 | 3.85% | 6.28% | 0.63 | -2.04% | 22,182.97 | 13 | 217.18 |

Главный результат: calibrated dynamic Aave hedge не максимизирует final NAV, но существенно улучшает downside risk относительно plain LP. Plain LP показал final NAV 104,405 USDC и max drawdown -35.70%, тогда как calibrated dynamic hedge показал final NAV 103,761 USDC и max drawdown только -2.04%.

Это означает, что стратегия не является “return-maximizing” модификацией LP. Её ценность — в снижении volatility и drawdown. На выбранном historical sample fixed hedge оказался сильнейшим baseline по final NAV и Sharpe, а calibrated dynamic hedge дал лучший downside protection.

### 15.1.1. Фактические результаты historical backtest на fractal-defi

Финальный historical backtest был запущен через `strategy.fractal_runner`. В этой версии AMM LP-leg моделируется через `fractal-defi`, а Aave hedge accounting реализован поверх fractal LP state.

Base run:

```bash
python -m strategy.fractal_runner \
  --data-path data/processed/market_data.csv \
  --output-dir reports/results_tables
```

Calibrated run:

```bash
python -m strategy.fractal_runner \
  --data-path data/processed/market_data.csv \
  --output-dir reports/results_tables/fractal_calibrated \
  --hedge-ratio 0.8499892802109696 \
  --rebalance-threshold 0.06965934324744885 \
  --slippage-bps 10 \
  --gas-cost-usdc 15
```

Calibrated dynamic hedge использует более высокий hedge ratio и более частый rebalance:

| Parameter           | Base dynamic | Calibrated dynamic |
| ------------------- | -----------: | -----------------: |
| Hedge ratio         |         0.75 |               0.85 |
| Rebalance threshold |        10.0% |               7.0% |
| Rebalances          |            8 |                 13 |
| Turnover            |    19,346.97 |          22,182.97 |
| Total costs         |       139.35 |             217.18 |

Калибровка улучшила dynamic strategy: final NAV вырос примерно на 980 USDC, Sharpe ratio увеличился с 0.44 до 0.63, а max drawdown снизился примерно в два раза — с -4.11% до -2.04%.

Однако calibrated dynamic hedge всё равно уступил fixed hedge по final NAV и Sharpe. Это важный результат: на данном периоде значительная часть пользы приходила от самого факта наличия hedge, а не от динамического ребалансирования. Dynamic rebalancing добавил лучший downside control, но увеличил turnover и transaction costs.

### 15.1.2. Results by market regime

Regime-level analysis нужен, чтобы проверить, где именно hedge приносит пользу. Поскольку режимы в датасете не всегда идут непрерывными блоками, ниже используется `compounded_return_inside_regime` и `local_max_drawdown_inside_regime`, а не простой return от первого до последнего timestamp режима.

Для читаемости в таблице оставлены только основные метрики: return внутри режима, local max drawdown, rebalances и costs для calibrated dynamic hedge.

| Regime        | Buy & Hold Return | Plain LP Return | Fixed Hedge Return | Dynamic Hedge Return | Plain LP Local DD | Dynamic Local DD | Dynamic Rebalances | Dynamic Costs |
| ------------- | ----------------: | --------------: | -----------------: | -------------------: | ----------------: | ---------------: | -----------------: | ------------: |
| Downtrend     |           -57.15% |         -59.32% |             -9.42% |               -7.17% |           -33.57% |           -1.82% |                  7 |        116.44 |
| High-vol chop |            11.42% |          14.06% |              2.91% |                2.43% |           -32.09% |           -1.93% |                  1 |         16.37 |
| Sideways      |            -9.00% |          -4.00% |              2.50% |                2.54% |           -32.52% |           -1.74% |                  1 |         17.18 |
| Uptrend       |           116.80% |         134.71% |             11.02% |                6.47% |           -31.55% |           -1.73% |                  4 |         67.19 |

Regime analysis показывает несколько важных эффектов.

Во-первых, hedge особенно полезен в downtrend. Plain LP внутри downtrend regime потерял около -59.32%, тогда как calibrated dynamic hedge потерял только -7.17%. Local drawdown снизился с -33.57% у plain LP до -1.82% у dynamic hedge. Это основной аргумент в пользу стратегии как risk-management layer.

Во-вторых, в sideways regime dynamic hedge показал положительный результат 2.54%, тогда как plain LP дал -4.00%. Это соответствует исходной гипотезе: в боковом рынке LP получает fees, а hedge снижает directional exposure.

В-третьих, в uptrend plain LP и buy & hold ожидаемо выигрывают по доходности. Plain LP дал 134.71%, buy & hold — 116.80%, тогда как dynamic hedge — только 6.47%. Это объясняется тем, что hedge создаёт short ETH exposure и ограничивает upside в растущем рынке.

В-четвёртых, fixed hedge остаётся сильным baseline. Он не несёт rebalancing costs и в ряде режимов даёт лучший return, чем dynamic hedge. Однако dynamic hedge показывает более низкий local drawdown почти во всех основных режимах. Следовательно, dynamic hedge лучше интерпретировать не как способ максимизации доходности, а как более активный механизм контроля downside risk.

Важно не переинтерпретировать Sharpe by regime. Для отдельных режимов, особенно если observations не образуют непрерывный временной интервал, annualized Sharpe может быть нестабильным и давать экстремальные значения. Поэтому в основном тексте используются return, local drawdown, rebalances и costs.

### 15.2. Equity curve interpretation

Plain LP показывает более высокий final NAV, чем calibrated dynamic hedge, но его equity curve значительно более волатильна. Это видно по annualized volatility 36.17% и max drawdown -35.70%. Calibrated dynamic hedge имеет более низкий final NAV, но гораздо более гладкую equity curve: annualized volatility 6.28% и max drawdown -2.04%.

Поэтому визуальный вывод по equity curve: dynamic hedge сглаживает траекторию NAV и снижает directional ETH exposure, но ограничивает upside в периоды роста ETH.

### 15.3. Drawdown interpretation

Drawdown — ключевая метрика проекта. Стратегия проверяется не как способ получить максимальный PnL, а как способ сделать LP-позицию менее уязвимой к направленным движениям ETH.

Сравнение max drawdown:

| Strategy                         |  Max DD |
| -------------------------------- | ------: |
| Buy & Hold 50/50                 | -32.48% |
| Plain Uniswap V2 LP              | -35.70% |
| Fixed Hedge LP                   |  -4.13% |
| Calibrated Dynamic Aave Hedge LP |  -2.04% |

Calibrated dynamic hedge показал лучший drawdown profile среди всех стратегий. Это главный положительный результат проекта: Aave hedge резко уменьшает downside risk plain LP.

### 15.4. PnL decomposition

PnL стратегии можно представить как:

```text
Net PnL = LP fees - Impermanent loss - Aave borrow cost + Aave supply yield - Gas costs - Slippage costs
```

Plain LP выигрывает за счёт полной экспозиции к LP fee income и отсутствия hedge costs, но остаётся сильно подвержен impermanent loss и directional risk. Dynamic hedge снижает directional risk, но платит за это rebalancing turnover, gas и slippage.

В calibrated run dynamic hedge выполнил 13 rebalances, создал turnover около 22,183 USDC и понёс total costs около 217 USDC. Эти costs небольшие относительно initial capital, но они показывают, что risk control не является бесплатным.

### 15.5. Hedge quality

Качество hedge оценивается через соответствие:

```text
LP_ETH_delta_t
vs
borrowed_WETH_t
```

и через hedge error:

```text
hedge_error_t =
abs(target_weth_debt_t - current_weth_debt_t) / LP_ETH_delta_t
```

Калиброванная стратегия использует `hedge_ratio ≈ 0.85` и `rebalance_threshold ≈ 7%`. Это означает, что она сильнее хеджирует LP ETH exposure, чем базовая dynamic version, и чаще корректирует WETH debt.

Факт 13 rebalances показывает, что стратегия действительно оставалась dynamic, а не превратилась в fixed hedge. При этом average health factor около 1.97 означает, что стратегия сохраняла запас относительно liquidation risk, но использовала Aave debt достаточно активно.

### 15.6. Regime-level interpretation

Режимный анализ подтверждает частичную гипотезу проекта.

В downtrend hedge работает лучше всего: он существенно сокращает потери plain LP и снижает local drawdown. В sideways market hedge также полезен: стратегия остаётся положительной, пока plain LP показывает отрицательный результат. В high-volatility chop plain LP имеет более высокий return, но его drawdown остаётся намного хуже, чем у hedged strategies.

В uptrend hedge ограничивает upside. Это ожидаемый trade-off: borrowed WETH создаёт short ETH exposure, поэтому стратегия не может полностью участвовать в росте ETH. Следовательно, Aave hedge полезен не во всех режимах, а прежде всего там, где снижение downside risk важнее участия в сильном росте ETH.

### 15.7. Monte Carlo robustness check

Monte Carlo stress tests были запущены как дополнительная robustness-проверка calibrated dynamic strategy. В отличие от historical backtest, Monte Carlo не использует реальные рыночные данные, а генерирует synthetic paths для нескольких рыночных режимов. Поэтому результаты Monte Carlo интерпретируются не как прогноз доходности, а как стресс-тест механики стратегии.

В Monte Carlo использовались те же calibrated parameters, что и в historical backtest:

```text
hedge_ratio ≈ 0.85
rebalance_threshold ≈ 7%
slippage_bps = 10
gas_cost_usdc = 15
```

Dynamic strategy действительно оставалась dynamic: в synthetic scenarios она выполняла ненулевое число ребалансировок, создавала turnover и несла transaction costs. Это важно, потому что Monte Carlo проверяет не fixed hedge, а полноценную dynamic hedge логику.

#### Dynamic hedge behaviour in Monte Carlo

| Scenario         | Median Final NAV | Median Max DD | Median Rebalances | Median Turnover | Median Costs |
| ---------------- | ---------------: | ------------: | ----------------: | --------------: | -----------: |
| crash_recovery   |       164,578.93 |       -67.30% |               167 |      244,094.10 |     2,796.30 |
| high_vol_chop    |        92,316.07 |       -59.28% |               193 |      263,270.65 |     3,203.41 |
| sideways_low_vol |       110,055.47 |       -38.43% |                57 |       86,073.61 |       948.31 |
| strong_downtrend |       169,057.23 |       -56.19% |                96 |      169,534.01 |     1,624.93 |
| strong_uptrend   |       138,440.49 |       -50.56% |                91 |      162,066.59 |     1,527.07 |

Monte Carlo показывает, что в synthetic regimes dynamic hedge становится гораздо активнее, чем в historical backtest. В historical calibrated run стратегия сделала 13 rebalances, а в Monte Carlo median rebalances варьируются от 57 до 193 в зависимости от сценария. Это связано с тем, что synthetic paths специально создают более стрессовые движения цены, TVL и liquidity.

#### Comparison with plain LP

Главная метрика Monte Carlo — не только final NAV, а improvement по drawdown относительно plain LP.

| Scenario         | Dynamic − Plain Final NAV, median | Positive NAV Share | Drawdown Improvement, median | Positive Drawdown Improvement Share |
| ---------------- | --------------------------------: | -----------------: | ---------------------------: | ----------------------------------: |
| crash_recovery   |                        -59,260.49 |             50.00% |                   14.77 p.p. |                             100.00% |
| high_vol_chop    |                          8,412.98 |             66.67% |                   17.00 p.p. |                             100.00% |
| sideways_low_vol |                         -5,449.44 |             50.00% |                   24.18 p.p. |                             100.00% |
| strong_downtrend |                        -48,073.52 |             25.00% |                   23.27 p.p. |                             100.00% |
| strong_uptrend   |                        -80,496.78 |             33.33% |                   13.45 p.p. |                             100.00% |

Monte Carlo подтверждает основной вывод historical backtest: dynamic Aave hedge не является стабильным механизмом максимизации final NAV. В части scenarios plain LP сохраняет более высокий upside, особенно когда synthetic path создаёт сильный положительный tail. Однако dynamic hedge во всех сценариях улучшает max drawdown относительно plain LP: positive drawdown improvement share равен 100% во всех пяти scenarios.

Это означает, что Monte Carlo поддерживает risk-management интерпретацию стратегии. Dynamic hedge стабильно снижает downside risk, но не гарантирует превосходство по final NAV.

#### Comparison with fixed hedge

Dynamic hedge не доминирует fixed hedge. В некоторых scenarios dynamic strategy проигрывает fixed hedge по final NAV из-за rebalancing costs и turnover. Это согласуется с historical result: fixed hedge является сильным baseline, потому что значительная часть эффекта приходит от самого снижения ETH exposure, а не от частого rebalance.

При этом dynamic hedge полезен тем, что адаптирует WETH debt к меняющейся LP delta. Это особенно важно в stress scenarios, где LP exposure быстро меняется. Стоимость этой адаптации — более высокий turnover и transaction costs.

#### Monte Carlo limitations

Monte Carlo results нужно интерпретировать осторожно. Synthetic paths не являются прогнозом рынка. Они задают искусственные режимы и могут создавать экстремальные tail outcomes, особенно в scenarios с высокой volatility и liquidity noise. Поэтому Monte Carlo используется только как robustness check, а не как основной источник performance claims.

Кроме того, некоторые диагностические метрики hedge error в synthetic paths могут быть чувствительны к конкретной генерации liquidity и TVL. В основной интерпретации используются более устойчивые метрики: final NAV, max drawdown, rebalances, turnover и total costs.

Итог по Monte Carlo: результаты подтверждают, что dynamic Aave hedge стабильно улучшает drawdown profile относительно plain LP, но не всегда улучшает final NAV. Это усиливает главный вывод проекта: стратегия является risk-management improvement, а не безусловной return-maximizing strategy.

### 15.8. Research questions answered

1. **Побеждает ли Aave-hedged LP plain LP по final NAV?**
   Не в calibrated historical run. Plain LP имеет final NAV 104,405 USDC, а calibrated dynamic hedge — 103,761 USDC.

2. **Улучшает ли hedge risk profile?**
   Да. Max drawdown plain LP составляет -35.70%, а calibrated dynamic hedge — только -2.04%.

3. **Добавляет ли dynamic rebalancing ценность относительно fixed hedge?**
   Не по final NAV и не по Sharpe на выбранном периоде. Fixed hedge остаётся сильнее по этим метрикам. Однако dynamic hedge показывает лучший downside protection: max drawdown -2.04% против -4.13% у fixed hedge.

4. **Где стратегия работает лучше всего?**
   В downtrend и sideways regimes. В downtrend dynamic hedge снижает потери с -59.32% у plain LP до -7.17%. В sideways regime dynamic hedge даёт +2.54%, тогда как plain LP даёт -4.00%.

5. **Где стратегия работает хуже?**
   В uptrend. Plain LP и buy & hold выигрывают за счёт long ETH exposure, а dynamic hedge ограничивает upside из-за short WETH debt.

6. **Подтверждена ли гипотеза?**
   Частично. Стратегия подтверждается как risk-management improvement для plain LP, но не как стратегия максимизации absolute return.

7. **Что добавил Monte Carlo?**  
   Monte Carlo подтвердил risk-management вывод: dynamic hedge не всегда выигрывает у plain LP по final NAV, но во всех synthetic scenarios улучшает max drawdown относительно plain LP.

### 15.9. Final interpretation

Итоговый вывод проекта: Aave-хеджированная LP-стратегия не создаёт безрисковую доходность и не доминирует plain LP по final NAV. Однако она существенно улучшает риск-профиль LP-позиции.

Plain LP оказался лучше calibrated dynamic hedge по final NAV, но имел max drawdown около -35.70%. Calibrated dynamic hedge снизил max drawdown до -2.04%, annualized volatility до 6.28% и сохранил положительный PnL. Это подтверждает, что Aave hedge полезен как инструмент управления downside risk.

Fixed hedge оказался сильным baseline: он дал лучший final NAV и Sharpe среди hedged versions. Это означает, что на выбранном historical sample значительная часть эффекта объясняется самим снижением ETH exposure, а не частым dynamic rebalancing. Тем не менее dynamic hedge дал наиболее контролируемый drawdown profile и лучше всего соответствует conservative risk-management задаче.

Monte Carlo robustness check усиливает этот вывод. В synthetic scenarios dynamic hedge не всегда превосходит plain LP по final NAV, но стабильно улучшает drawdown profile. Поэтому итоговая интерпретация остаётся прежней: Aave hedge полезен прежде всего как механизм контроля downside risk.

Финальная формулировка гипотезы: частичный Aave hedge действительно может улучшить risk-adjusted profile plain Uniswap V2 LP, но его основная ценность — снижение drawdown и volatility, а не максимизация абсолютной доходности.

---

## 16. Strategy improvement

Предлагаемая стратегия улучшает plain Uniswap V2 LP не за счёт устранения impermanent loss, а за счёт снижения направленной ETH exposure. Plain LP получает комиссии, но остаётся уязвимым к сильным движениям цены ETH. Aave hedge добавляет short ETH exposure, который должен частично компенсировать потери LP в downtrend и high-volatility regimes.

Преимущество стратегии проявляется в трёх аспектах:

1. **Risk reduction** — частичный hedge должен снижать directional exposure и max drawdown.
2. **Fee preservation** — стратегия продолжает получать AMM fees.
3. **Dynamic adjustment** — hedge пересчитывается по LP delta, а не фиксируется навсегда.

При этом стратегия может проигрывать plain LP, если funding, gas и slippage оказываются выше выгоды от hedge. Поэтому в проекте делается акцент на честном сравнении с baseline и sensitivity analysis.

После калибровки improvement стратегии формулируется точнее. Dynamic Aave hedge не доминирует plain LP по final NAV, но существенно улучшает risk profile. Calibrated dynamic hedge снижает max drawdown с -35.70% у plain LP до -2.04%, а annualized volatility — с 36.17% до 6.28%.

Это означает, что стратегия полезна прежде всего для инвестора, который готов пожертвовать частью upside и fee-driven return ради более стабильной equity curve и меньшего downside risk.

При этом fixed hedge остаётся сильным baseline. В нашем historical backtest fixed hedge дал более высокий final NAV и Sharpe ratio, чем dynamic hedge. Следовательно, добавленная ценность dynamic rebalancing не является безусловной: она зависит от выбранного периода, costs, threshold и характера price path.

---

## 17. Limitations

Результаты проекта следует интерпретировать с учётом нескольких ограничений.

Во-первых, Aave funding leg моделируется через SOFR-based proxy, а не через фактическую историю WETH borrow и USDC supply rates в Aave V3. Это ограничивает точность моделирования funding cost, но делает assumption воспроизводимым и прозрачным.

Во-вторых, Uniswap V2 WETH/USDC pool уже не является единственным и наиболее современным источником ETH/USDC liquidity. Снижение TVL в течение периода указывает на liquidity migration risk.

В-третьих, fee income сильно зависит от отдельных high-volume stress events. Поэтому результаты backtest могут быть чувствительны к нескольким экстремальным часам.

В-четвёртых, backtest не моделирует все production risks: MEV, failed transactions, keeper delay, oracle manipulation, smart contract exploits и реальную динамику gas price.

В-пятых, Monte Carlo scenarios являются стресс-тестом, а не прогнозом будущей доходности.

В-шестых, Sepolia deployment не является production validation. Он показывает, что архитектура vault может быть выражена в Solidity и проходит smoke-test, но не моделирует реальные Uniswap V2 Router, реальные Aave V3 Pool interfaces, oracle latency, MEV, production keeper logic и liquidation execution. Production deployment потребовал бы замены mock interfaces на реальные protocol interfaces и отдельного security review.

---

Ещё одно ограничение связано с калибровкой. Optuna-калибровка проводилась на том же историческом периоде, который используется для final comparison, поэтому calibrated parameters могут содержать in-sample bias. Чтобы уменьшить этот риск, search space ограничивался только двумя strategy-control параметрами: `hedge_ratio` и `rebalance_threshold`. Gas, slippage, LTV, health factor и circuit breaker threshold не оптимизировались.

Дополнительно широкий поиск показал, что при слишком высоком rebalance threshold dynamic hedge может фактически превращаться в fixed hedge. Поэтому calibrated threshold должен интерпретироваться не как универсально оптимальный параметр, а как результат для конкретного historical sample и заданной objective function.
---

## 18. References

### 18.1. Protocol documentation

1. **Uniswap V2 documentation / Uniswap Labs materials** — используется для описания логики Uniswap V2 LP, full-range liquidity, fee tier и роли liquidity providers.
2. **Uniswap V2 whitepaper** — используется для описания constant product AMM, формулы $x \cdot y = k$, LP pricing и механики пула.
3. **Aave V3 documentation** — используется для описания lending/borrowing, collateral, debt, health factor, liquidation threshold и liquidation risk.
4. **Aave Health Factor and Liquidations documentation** — используется для формулы health factor и объяснения liquidation risk.
5. **fractal-defi documentation / GitHub repository** — используется как основной backtesting framework.

### 18.2. Data sources

6. **Binance ETHUSDC historical data** — используется для ETH/USDC price series.
7. **The Graph / Uniswap V2 subgraph data** — используется для получения данных по Uniswap V2 pool: TVL, volume, liquidity и fees.
8. **FRED SOFR series** — используется как SOFR-based funding proxy для Aave borrow/supply assumptions.

### 18.3. Academic and technical materials

9. **Impermanent loss explainers and AMM research materials** — используются для интерпретации LP payoff, negative gamma exposure и сравнения LP с buy & hold.
10. **AMM liquidity provision research** — используется для объяснения trade-off между fee income и adverse selection / impermanent loss.

### 18.4. Previous internal work

11. **Solidity vault prototype: Impermanent Loss Hedging Vault** — используется как предыдущий prototype стратегии Uniswap V2 ETH/USDC LP + Aave hedge.
12. **Previous Uniswap V3 hedge homework** — используется как источник опыта по backtesting, hedge logic и regime analysis.
13. **Aave DeFi EDA notebook** — используется для мотивации выбора Aave V3 и описания lending/borrowing data.

### 18.5. Как источники использовались в проекте

| Категория | Источник | Как использовался |
|---|---|---|
| Protocol mechanics | Uniswap V2 whitepaper / docs | Формализация AMM, constant product model, LP fees |
| Lending / borrowing risk | Aave V3 docs | Health factor, LTV, liquidation threshold, borrow/supply logic |
| Market data | Binance ETHUSDC | Исторический ценовой ряд ETH/USDC |
| On-chain pool data | The Graph / Uniswap subgraph | TVL, volume, liquidity, estimated pool fees |
| Funding proxy | FRED SOFR | Воспроизводимый proxy для Aave funding leg |
| Backtesting framework | fractal-defi | AMM LP simulation layer |
| Solidity testing | Foundry / Forge | Vault prototype tests and Sepolia mock deployment |
| Academic background | IL / AMM hedging papers | Обоснование impermanent loss, negative gamma и hedge logic |

---

## 19. LLM transparency

### 19.1. Purpose of LLM usage

LLM использовалась как вспомогательный инструмент для:

- структурирования проекта;
- составления черновика whitepaper;
- формулировки research questions;
- подготовки pseudocode;
- составления checklist требований;
- помощи с архитектурой репозитория;
- scaffolding кода;
- формулировки limitations и risk management.

LLM не используется как самостоятельный источник истины для финальных результатов.

### 19.2. Human contribution

Авторы проекта самостоятельно принимают и проверяют ключевые решения:

- выбор темы;
- выбор стратегии;
- выбор Uniswap V2 вместо Uniswap V3;
- выбор Aave V3 как hedge venue;
- выбор baselines;
- выбор параметров backtest;
- запуск кода;
- проверка результатов;
- интерпретация метрик;
- финальные выводы.

### 19.3. Validation process

Чтобы снизить риск ошибок, возникших из-за LLM-generated content, в проекте используется manual validation:

1. Формулы проверяются через unit tests.
2. Accounting проверяется через отдельные tests.
3. Rebalance rule фиксируется до просмотра результатов.
4. Все costs явно включаются в NAV.
5. Idle tokens отдельно отслеживаются.
6. Backtest сравнивается с несколькими baseline.
7. Финальные выводы делаются только после получения результатов.
8. Все спорные assumptions фиксируются в `transparency/design_decisions.md`.

### 19.4. Transcript

Для воспроизводимости в репозиторий добавляется файл:

```text
transparency/llm_transcript.md
```

В нём сохраняется полный или сокращённый чат-транскрипт работы с LLM.

Также добавляется файл:

```text
transparency/human_contributions.md
```

В нём фиксируется, какие части проекта были выполнены авторами вручную.

