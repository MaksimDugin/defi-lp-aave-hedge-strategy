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

Базовое значение threshold:

$$
\theta = 10\%.
$$

Если текущий WETH debt ниже целевого, стратегия занимает дополнительный WETH через Aave V3 и продаёт его в USDC. Если текущий WETH debt выше целевого, стратегия покупает WETH за USDC и погашает часть долга.

### 6.5. NAV стратегии

Стоимость стратегии считается в USDC. Полный NAV включает LP-позицию, Aave collateral, Aave debt, idle tokens и накопленные costs:

$$
NAV_t =
V_{LP,t}
+ C_{Aave,t}
- D_{Aave,t}
+ Idle_t
- Costs_t.
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

