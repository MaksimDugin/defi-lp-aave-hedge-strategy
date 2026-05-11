# Aave-хеджированная LP-стратегия ETH/USDC

## 1. Аннотация

В проекте реализуется и тестируется консервативная DeFi-стратегия предоставления ликвидности в Uniswap V2 ETH/USDC с частичным хеджированием через Aave V3. Стратегия делит капитал между LP-позицией и collateral reserve, занимает WETH в Aave V3 и использует этот заём как short ETH exposure для снижения направленного риска LP-позиции.

Стратегия сравнивается с buy & hold 50/50 ETH/USDC, plain Uniswap V2 LP и LP с fixed initial hedge. Проверка проводится на исторических данных и через Monte Carlo stress tests для разных рыночных режимов.



## 2. Постановка проблемы

Поставщики ликвидности в Uniswap V2 получают комиссионный доход от сделок в пуле, но одновременно несут риск impermanent loss. Для ETH/USDC LP-позиция ведёт себя как автоматически ребалансируемый портфель: при росте ETH пул продаёт ETH, а при падении ETH покупает ETH. Из-за этого LP-позиция имеет отрицательную gamma exposure и может проигрывать простой стратегии buy & hold при сильном направленном движении цены.

Цель проекта — проверить, может ли частичный hedge через Aave V3 улучшить результат plain Uniswap V2 LP. Для этого стратегия занимает WETH под USDC collateral и использует borrowed WETH как short ETH exposure против ETH-delta LP-позиции.



## 3. Гипотеза стратегии

Основная гипотеза состоит в том, что частичное хеджирование ETH exposure через Aave V3 может улучшить результат plain Uniswap V2 LP, сохранив доход от AMM-комиссий и снизив направленный риск ETH.

Ожидается, что стратегия будет лучше работать в боковых и умеренно волатильных режимах, где комиссионный доход LP способен компенсировать Aave borrow cost, gas costs и slippage. В сильном тренде стратегия может уступать buy & hold и даже plain LP из-за стоимости хеджа и отрицательной gamma LP-позиции.



## 4. Инструменты стратегии

В проекте используются следующие инструменты:

- Uniswap V2 ETH/USDC pool — площадка для предоставления ликвидности;
- Aave V3 — протокол lending/borrowing для открытия hedge;
- USDC — accounting currency и collateral asset;
- WETH — borrowed asset, используемый для short ETH exposure;
- `fractal-defi` — библиотека для реализации воспроизводимого backtest.



## 5. Связь с предыдущими проектами

Финальный проект развивает идеи двух предыдущих работ. В Solidity vault prototype уже была реализована базовая логика Uniswap V2 LP + Aave hedge: расчёт LP delta, `rebalance()`, health factor, LTV constraints и circuit breaker. В предыдущем ДЗ по Uniswap V3 была протестирована идея LP-стратегии с хеджированием и анализом рыночных режимов.

В финальном проекте эти идеи переносятся в воспроизводимый research-backtest на исторических данных. Основной фокус смещается с архитектуры vault на проверку экономической гипотезы: может ли Aave-хедж улучшить plain Uniswap V2 LP после учёта funding, gas, slippage и риска ребалансировки.

Ниже готовые разделы для вставки в `reports/whitepaper.md` после раздела **5. Связь с предыдущими проектами**.



## 6. Формальное описание стратегии

### 6.1. Общая идея

Стратегия строится вокруг LP-позиции в Uniswap V2 ETH/USDC и частичного хеджирования её ETH exposure через Aave V3. LP-позиция зарабатывает комиссии от торгового объёма в пуле, но несёт риск impermanent loss и направленный риск ETH. Чтобы снизить этот риск, стратегия занимает WETH в Aave V3 под USDC collateral и использует этот заём как short ETH exposure.

Начальный капитал делится на две части:

- 50% капитала направляется в Uniswap V2 ETH/USDC LP;
- 50% капитала используется как collateral / hedge reserve в Aave V3.

Borrowed WETH считается реальным short ETH: предполагается, что после займа WETH продаётся в USDC. Это позволяет компенсировать часть ETH exposure LP-позиции.

### 6.2. LP-позиция в Uniswap V2

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

### 6.3. Target hedge

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

Для sensitivity analysis дополнительно рассматривается:

$$
h \in \{0.50, 0.75\}.
$$

### 6.4. Rebalance rule

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

Базовое значение threshold 10%.

Если текущий WETH debt ниже целевого, стратегия занимает дополнительный WETH через Aave V3 и продаёт его в USDC. Если текущий WETH debt выше целевого, стратегия покупает WETH за USDC и погашает часть долга.

### 6.5. NAV стратегии

Стоимость стратегии считается в USDC. Полный NAV включает LP-позицию, Aave collateral, Aave debt, idle tokens и накопленные costs:

$$
NAV_t =
V_{LP,t}
+C_{Aave,t}
-D_{Aave,t}
+Idle_t
-Costs_t.
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

### 6.6. PnL decomposition

Итоговый PnL стратегии раскладывается на несколько компонентов:

$$
NetPnL =
LPFees
- ImpermanentLoss
- AaveBorrowCost
+ AaveSupplyYield
- GasCosts
- SlippageCosts.
$$

Основной источник доходности стратегии — комиссии Uniswap V2. Основные источники потерь — impermanent loss, стоимость займа WETH в Aave, gas costs, slippage и издержки ребалансировки.

Таким образом, стратегия может быть успешной только если доход от AMM-комиссий и эффект снижения directional exposure превышают стоимость hedge и execution costs.

### 6.7. Risk constraints

Стратегия использует несколько ограничений риска:

1. **LTV limit**  
   Стратегия не должна превышать максимальный loan-to-value в Aave.

2. **Minimum health factor**  
   Если health factor приближается к опасному уровню, стратегия не увеличивает debt и может частично погасить WETH debt.

3. **Circuit breaker**  
   При резких движениях цены, падении ликвидности, росте borrow APY или ухудшении health factor стратегия приостанавливает увеличение hedge.

4. **Gas-aware rebalance**  
   Rebalance выполняется только если ожидаемая польза от корректировки hedge превышает execution costs.

5. **Idle token accounting**  
   Все неиспользуемые токены включаются в NAV и отдельно отслеживаются через idle ratio.



## 7. Pseudocode

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
    Update Aave V3 lending and borrowing rates

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
````



## 8. Baseline comparison

Для оценки качества стратегии используются три baseline. Это необходимо, чтобы отделить эффект LP-комиссий, эффект хеджирования и эффект динамической ребалансировки.

### 8.1. Baseline 1: Buy & Hold 50/50 ETH/USDC

Первый baseline — простая стратегия buy & hold. Начальный капитал делится между ETH и USDC в пропорции 50/50. После этого портфель не ребалансируется и не использует DeFi-протоколы.

Стоимость портфеля в момент времени (t):

$$
V^{BH}*t = q*{ETH,0} \cdot P_t + q_{USDC,0},
$$

где:

* $q_{ETH,0}$ — начальное количество ETH;
* $q_{USDC,0}$ — начальное количество USDC;
* $P_t$ — цена ETH в USDC.

Этот baseline показывает, как стратегия выглядит по сравнению с простой пассивной экспозицией к ETH/USDC без impermanent loss, funding costs и transaction costs.



### 8.2. Baseline 2: Plain Uniswap V2 ETH/USDC LP

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

### 8.3. Baseline 3: LP with fixed initial hedge

Третий baseline — LP-позиция с фиксированным начальным hedge. В начале периода стратегия открывает LP-позицию, рассчитывает начальную ETH-delta и занимает WETH через Aave V3. После этого hedge не ребалансируется.

Целевой начальный hedge:

$$
D^{fixed}*{WETH,0} = h \cdot \Delta*{LP,0}.
$$

Для всех последующих моментов времени:

$$
D^{fixed}*{WETH,t} = D^{fixed}*{WETH,0}.
$$

Этот baseline нужен, чтобы отделить эффект самого hedge от эффекта динамической ребалансировки. Если dynamic hedge показывает лучший результат, чем fixed hedge, значит ребалансировка добавляет ценность. Если fixed hedge оказывается не хуже, значит частая ребалансировка может быть экономически неоправданной из-за gas и slippage.

### 8.4. Main strategy: Dynamic Aave-hedged LP

Основная стратегия отличается от fixed hedge тем, что регулярно пересчитывает LP ETH-delta и корректирует WETH debt.

Целевой debt:

$$
D^{target}*{WETH,t} = h \cdot \Delta*{LP,t}.
$$

Rebalance выполняется только если:

$$
HE_t > \theta.
$$

При этом стратегия учитывает:

* Aave borrow cost;
* Aave collateral yield;
* gas costs;
* slippage;
* health factor;
* LTV;
* circuit breaker;
* idle tokens.

### 8.5. Критерии сравнения

Стратегии сравниваются не только по финальному PnL, но и по risk-adjusted metrics.

Основные метрики:

* final NAV;
* net PnL;
* annualized return;
* annualized volatility;
* Sharpe ratio;
* max drawdown;
* turnover;
* number of rebalances;
* total LP fees;
* total Aave borrow cost;
* total gas costs;
* total slippage costs;
* average health factor;
* average idle ratio.

Главная цель стратегии — показать улучшение относительно plain Uniswap V2 LP. Улучшение может проявляться в нескольких формах:

1. более высокий final NAV;
2. более высокий Sharpe ratio;
3. меньший max drawdown;
4. меньшая volatility;
5. лучшая устойчивость в отдельных рыночных режимах.

Финальный вывод строится не только на том, победила ли стратегия baseline по доходности, но и на том, насколько оправданным оказался trade-off между LP fee income и hedge costs.

## 9. Backtesting protocol

### 9.1. Цель backtest

Backtest нужен для проверки, улучшает ли Aave-хеджированная LP-стратегия результат plain Uniswap V2 ETH/USDC LP после учёта всех основных издержек:

* impermanent loss;
* Aave borrow cost;
* Aave supply yield;
* gas costs;
* slippage;
* rebalancing turnover;
* idle token inefficiency.

Главное сравнение проводится между:

1. Buy & Hold 50/50 ETH/USDC;
2. plain Uniswap V2 ETH/USDC LP;
3. LP с fixed initial hedge;
4. dynamic Aave-hedged LP.

Основной benchmark — **plain Uniswap V2 LP**, потому что наша стратегия является его модификацией.

### 9.2. Начальные условия

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

### 9.3. Частота backtest

Основная частота backtest выбирается исходя из доступности и качества данных.

Базовый вариант:

```text
Frequency = hourly
```

Если hourly data по Aave или Uniswap оказываются неполными или нестабильными, используется daily frequency. В этом случае ограничение явно фиксируется в разделе Data limitations.

Hourly frequency предпочтительнее, потому что она лучше отражает:

* изменение цены ETH;
* накопление LP fees;
* изменение Aave borrow/supply rates;
* необходимость ребалансировки hedge;
* execution costs.

### 9.4. Execution assumptions

Backtest использует следующие execution assumptions:

1. Сделки исполняются по наблюдаемой цене на timestamp.
2. Slippage учитывается отдельно через фиксированную bps-модель.
3. Gas cost применяется к каждому действию, требующему транзакции:

   * LP entry;
   * LP exit;
   * borrow;
   * repay;
   * swap borrowed WETH to USDC;
   * swap USDC to WETH for repay;
   * rebalance.
4. Aave borrow cost начисляется на outstanding WETH debt.
5. Aave supply yield начисляется на USDC collateral.
6. Rebalance происходит только при выполнении threshold condition и risk checks.
7. Circuit breaker может заблокировать увеличение debt.
8. Все idle tokens включаются в NAV.

### 9.5. Transaction costs

В backtest учитываются три типа execution costs.

#### 1. Gas costs

Gas cost задаётся в USDC на каждую операцию:

```text
gas_cost_per_rebalance = fixed USDC amount
```

Для sensitivity analysis можно использовать несколько сценариев:

```text
low gas
medium gas
high gas
```

Пример:

```text
gas_cost_per_rebalance ∈ {5, 15, 30} USDC
```

#### 2. Slippage

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

#### 3. Aave funding

Aave funding cost считается на outstanding WETH debt:

```text
borrow_cost_t = WETH_debt_t × ETH_price_t × borrow_rate_t
```

Aave supply yield считается на USDC collateral:

```text
supply_yield_t = USDC_collateral_t × supply_rate_t
```

### 9.6. Rebalancing assumptions

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

Если целевой debt выше текущего, стратегия занимает дополнительный WETH и продаёт его в USDC.

Если целевой debt ниже текущего, стратегия покупает WETH за USDC и погашает часть Aave debt.

Rebalance не выполняется, если:

* circuit breaker активен;
* health factor ниже минимального уровня;
* LTV превышает лимит;
* ожидаемый эффект от rebalance меньше gas и slippage costs;
* данные на timestamp неполные.

### 9.7. Regime split

Результаты анализируются не только на всём периоде, но и по рыночным режимам.

Основные режимы:

```text
1. ETH uptrend
2. ETH downtrend
3. Sideways low-volatility market
4. High-volatility chop
5. Crash and recovery
```

Regime split нужен, потому что стратегия не обязана одинаково хорошо работать во всех условиях. Ожидается, что Aave hedge будет полезнее в боковом и волатильном рынке, где LP fees могут компенсировать funding и execution costs. В сильном направленном тренде hedge может ухудшать результат из-за стоимости займа и отрицательной gamma LP-позиции.

### 9.8. Monte Carlo stress tests

Помимо исторического backtest, стратегия проверяется на Monte Carlo scenarios. Цель Monte Carlo — не заменить historical data, а показать устойчивость стратегии в разных искусственно заданных рыночных режимах.

Сценарии:

```text
1. Strong ETH uptrend
2. Strong ETH downtrend
3. Sideways low-volatility
4. High-volatility chop
5. Crash and recovery
```

Для каждого сценария сравниваются:

* final NAV;
* max drawdown;
* Sharpe ratio;
* number of rebalances;
* total funding cost;
* total gas and slippage costs;
* hedge error;
* health factor.

Monte Carlo results используются как robustness check.

## 10. Risk management

### 10.1. Основные риски стратегии

Стратегия несёт несколько типов риска:

1. **Impermanent loss risk**
   LP-позиция может проигрывать buy & hold при сильном изменении цены ETH.

2. **Funding risk**
   Стоимость займа WETH в Aave может оказаться выше дохода от LP fees.

3. **Liquidation risk**
   Если стоимость debt относительно collateral становится слишком высокой, Aave-позиция может приблизиться к liquidation threshold.

4. **Execution risk**
   Gas и slippage могут съесть выгоду от ребалансировки.

5. **Rebalance risk**
   Слишком частый rebalance увеличивает costs, слишком редкий rebalance оставляет большой directional exposure.

6. **Idle token risk**
   Часть капитала может лежать без работы и ухудшать capital efficiency.

7. **Liquidity risk**
   При падении ликвидности в пуле сделки могут исполняться с высоким slippage.

### 10.2. Rebalance caller

В production-логике `rebalance()` должен вызываться внешним исполнителем.

Возможные варианты:

* собственный keeper bot;
* публичная keeper-инфраструктура;
* permissionless вызов функции любым пользователем;
* полуавтоматический manual rebalance.

В рамках backtest используется deterministic rebalance:

```text
На каждом timestamp стратегия проверяет условия rebalance.
Если threshold и risk checks выполнены, rebalance считается исполненным.
```

Это допущение явно отделяет backtest от production deployment. В production нужно дополнительно учитывать задержки исполнения, MEV, failed transactions и keeper incentives.

### 10.3. Circuit breaker

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

Circuit breaker не делает стратегию безрисковой, но ограничивает действия, которые могут резко увеличить liquidation или execution risk.

### 10.4. LTV и health factor

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

### 10.5. Idle tokens

Idle tokens — это активы, которые находятся внутри стратегии, но не используются продуктивно.

В нашем проекте idle tokens могут быть:

* USDC, который не внесён в LP и не deposited в Aave;
* WETH, который остался после rebalance и не использован для repay;
* ETH/USDC leftovers после добавления ликвидности;
* USDC после продажи borrowed WETH, если он не используется как collateral или reserve.

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

### 10.6. Gas-aware rebalance

Rebalance выполняется только если ожидаемая польза от корректировки hedge оправдывает transaction costs.

Условие:

```text
expected_rebalance_benefit > gas_cost + slippage_cost
```

Если hedge error превышает threshold, но notional ребалансировки слишком мал, стратегия может пропустить rebalance. Это защищает backtest от нереалистично частой торговли.



### 10.7. Slippage limits

Для каждой сделки считается slippage cost:

```text
slippage_cost = trade_notional × slippage_bps / 10,000
```

Если estimated slippage превышает допустимый лимит, стратегия не выполняет rebalance.

Это важно для реалистичности, потому что Aave hedge требует swap-операций:

* borrowed WETH → USDC;
* USDC → WETH для repay.



## 11. Results interpretation

> Этот раздел заполняется после запуска historical backtest и Monte Carlo. Ниже структура, которую нужно оставить в whitepaper и заполнить фактическими числами.

### 11.1. Summary of results

В этом разделе сравниваются четыре стратегии:

1. Buy & Hold 50/50 ETH/USDC;
2. plain Uniswap V2 ETH/USDC LP;
3. LP with fixed initial hedge;
4. dynamic Aave-hedged LP.

Итоговая таблица:

```text
| Strategy | Final NAV | Net PnL | Ann. Return | Sharpe | Max DD | Turnover | Total Costs |
||:|:|:|:|:|:|:|
| Buy & Hold | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| Plain LP | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| Fixed Hedge LP | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| Dynamic Aave Hedge LP | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
```

Главный вопрос:

```text
Побеждает ли dynamic Aave-hedged LP стратегию plain Uniswap V2 LP после учёта costs?
```

### 11.2. Equity curve interpretation

Equity curve показывает динамику NAV стратегий во времени.

Если dynamic hedge показывает более плавную equity curve, это означает, что стратегия действительно снижает directional ETH exposure.

Если dynamic hedge отстаёт от plain LP, нужно проверить:

* был ли рынок сильным uptrend;
* были ли слишком высокие borrow costs;
* были ли слишком частые rebalances;
* насколько gas и slippage съели LP fee income.

### 11.3. Drawdown interpretation

Max drawdown показывает, насколько сильно стратегия проседала относительно предыдущего пика.

Ожидаемый результат:

```text
Dynamic Aave hedge должен иметь меньший max drawdown, чем plain LP, особенно в downtrend или high-volatility regimes.
```

Если max drawdown не снижается, возможные причины:

* hedge ratio слишком низкий;
* rebalance слишком редкий;
* Aave debt создаёт дополнительный риск;
* LP fees не компенсируют costs;
* circuit breaker срабатывает слишком поздно.



### 11.4. PnL decomposition

PnL decomposition показывает, какие компоненты сделали стратегию прибыльной или убыточной.

Основные компоненты:

```text
Net PnL =
LP fees
- Impermanent loss
- Aave borrow cost
+ Aave supply yield
- Gas costs
- Slippage costs
```

Если стратегия проигрывает plain LP, нужно определить, какой компонент стал главным источником потерь:

* слишком высокий Aave borrow cost;
* слишком большие gas costs;
* слишком частая ребалансировка;
* недостаточный LP fee income;
* слишком большой hedge ratio.

Если стратегия выигрывает plain LP, нужно показать, за счёт чего:

* снижение ETH directional exposure;
* меньший drawdown;
* достаточный LP fee income;
* адекватная частота rebalance;
* умеренный funding cost.



### 11.5. Hedge quality

Качество hedge оценивается через сравнение:

```text
LP_ETH_delta_t
vs
borrowed_WETH_t
```

И через hedge error:

```text
hedge_error_t =
abs(target_weth_debt_t - current_weth_debt_t) / LP_ETH_delta_t
```

Если hedge error часто высокий, значит стратегия недостаточно хорошо поддерживает target exposure.

Возможные причины:

* слишком высокий rebalance threshold;
* circuit breaker часто блокирует rebalance;
* gas-aware rule пропускает мелкие ребалансировки;
* Aave health factor ограничивает возможность увеличить debt.



### 11.6. Regime-level interpretation

Результаты нужно отдельно интерпретировать по режимам.

#### ETH uptrend

В сильном uptrend стратегия может отставать от buy & hold, потому что:

* LP продаёт ETH по мере роста цены;
* hedge создаёт short ETH exposure;
* borrow WETH становится дороже в USDC-выражении.

#### ETH downtrend

В downtrend hedge должен помогать, потому что short ETH exposure компенсирует часть потерь LP-позиции.

#### Sideways market

В боковом рынке стратегия потенциально наиболее сильна:

* LP собирает fees;
* impermanent loss ограничен;
* hedge не слишком дорогой;
* directional exposure ниже, чем у plain LP.

#### High-volatility chop

В high-volatility chop результат зависит от баланса:

```text
LP fees vs rebalance costs + funding costs
```

Если trading volume высокий, LP fees могут компенсировать costs. Если же rebalance слишком частый, стратегия может проиграть.



### 11.7. Monte Carlo interpretation

Monte Carlo stress tests используются для проверки robustness.

Нужно сравнить:

```text
- средний Final NAV;
- медианный Final NAV;
- worst-case percentile;
- max drawdown;
- частоту circuit breaker events;
- средний hedge error;
- средний health factor.
```

Если стратегия показывает лучший downside profile, но не всегда лучший final PnL, это всё равно важный результат. Тогда вывод формулируется как:

```text
Стратегия не создаёт бесплатную доходность, но может улучшать профиль риска plain LP в отдельных режимах.
```



### 11.8. Final interpretation template

После получения результатов финальный вывод можно оформить так:

```text
На историческом периоде dynamic Aave-hedged LP [превзошла / не превзошла] plain Uniswap V2 LP по final NAV. При этом стратегия показала [меньший / больший] max drawdown и [лучший / худший] Sharpe ratio.

Основным источником доходности были LP fees. Основными издержками стали Aave borrow cost, gas и slippage. Результаты показывают, что hedge имеет смысл в режимах, где снижение directional exposure компенсирует стоимость funding и execution.

Таким образом, гипотеза [подтверждается / частично подтверждается / не подтверждается] для выбранного периода и параметров.
```



## 12. References

### 12.1. Protocol documentation

1. **Uniswap V2 documentation / Uniswap Labs materials**
   Используется для описания логики Uniswap V2 LP, full-range liquidity, fee tier и роли liquidity providers.

2. **Uniswap V2 whitepaper**
   Используется для описания constant product AMM, формулы (x \cdot y = k), LP pricing и механики пула.

3. **Aave V3 documentation**
   Используется для описания lending/borrowing, collateral, debt, health factor, liquidation threshold и liquidation risk.

4. **Aave Health Factor and Liquidations documentation**
   Используется для формулы health factor и объяснения liquidation risk.

5. **fractal-defi documentation / GitHub repository**
   Используется как основной backtesting framework. В проекте применяются сущности Uniswap V2 LP и Aave для воспроизводимой реализации стратегии.



### 12.2. Data sources

6. **The Graph / Uniswap V2 subgraph data**
   Используется для получения данных по Uniswap V2 pool: TVL, volume, liquidity и fees.

7. **Aave V3 API / GraphQL data**
   Используется для получения WETH borrow APY и USDC supply APY.

8. **External ETH/USDC price source**
   Используется для проверки price series и оценки ETH-denominated exposure.



### 12.3. Academic and technical materials

9. **Impermanent loss explainers and AMM research materials**
   Используются для интерпретации LP payoff, negative gamma exposure и сравнения LP с buy & hold.

10. **AMM liquidity provision research**
    Используется для объяснения trade-off между fee income и adverse selection / impermanent loss.



### 12.4. Previous internal work

11. **Solidity vault prototype: Impermanent Loss Hedging Vault**
    Используется как предыдущий prototype стратегии Uniswap V2 ETH/USDC LP + Aave hedge.

12. **Previous Uniswap V3 hedge homework**
    Используется как источник опыта по backtesting, hedge logic и regime analysis.

13. **Aave DeFi EDA notebook**
    Используется для мотивации выбора Aave V3 и описания lending/borrowing data.



## 13. LLM transparency

### 13.1. Purpose of LLM usage

LLM использовалась как вспомогательный инструмент для:

* структурирования проекта;
* составления черновика whitepaper;
* формулировки research questions;
* подготовки pseudocode;
* составления checklist требований;
* помощи с архитектурой репозитория;
* scaffolding кода;
* формулировки limitations и risk management.

LLM не используется как самостоятельный источник истины для финальных результатов.



### 13.2. Human contribution

Авторы проекта самостоятельно принимают и проверяют ключевые решения:

* выбор темы;
* выбор стратегии;
* выбор Uniswap V2 вместо Uniswap V3;
* выбор Aave V3 как hedge venue;
* выбор baselines;
* выбор параметров backtest;
* запуск кода;
* проверка результатов;
* интерпретация метрик;
* финальные выводы.



### 13.3. Validation process

Чтобы снизить риск ошибок, возникших из-за LLM-generated content, в проекте используется manual validation:

1. Формулы проверяются через unit tests.
2. Accounting проверяется через отдельные tests.
3. Rebalance rule фиксируется до просмотра результатов.
4. Все costs явно включаются в NAV.
5. Idle tokens отдельно отслеживаются.
6. Backtest сравнивается с несколькими baseline.
7. Финальные выводы делаются только после получения результатов.
8. Все спорные assumptions фиксируются в `transparency/design_decisions.md`.



### 13.4. Transcript

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



### 13.5. Limitations of LLM assistance

LLM могла предложить некорректные формулы, неполные assumptions или слишком оптимистичную интерпретацию стратегии. Поэтому все ключевые элементы проекта должны быть проверены вручную:

* данные;
* параметры;
* формулы;
* код;
* метрики;
* графики;
* выводы.

Финальный результат проекта основывается не на утверждениях LLM, а на воспроизводимом backtest и проверяемой логике стратегии.

