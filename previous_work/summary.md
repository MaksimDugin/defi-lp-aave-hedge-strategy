# Краткое описание предыдущих проектов

## 1. Solidity vault prototype

В предыдущем проекте был реализован MVP-vault для стратегии Uniswap V2 ETH/USDC LP с хеджированием через Aave V3. Vault поддерживал внесение и вывод ликвидности, расчёт дельты LP-позиции, публичный `rebalance()`, базовые ограничения по LTV и health factor, slippage limits и circuit breaker.

Что берём в финальный проект:

- идею LP-позиции в Uniswap V2 ETH/USDC;
- математику impermanent loss и LP delta;
- идею хеджирования через заём WETH в Aave V3;
- логику периодического `rebalance()`;
- ограничения по LTV, health factor и circuit breaker.

Что меняем:

- Solidity vault не используется как основной backtest engine;
- финальная стратегия реализуется и тестируется через `fractal-defi`;
- добавляются исторические данные, baseline comparison, метрики и графики.

## 2. Предыдущее ДЗ по Uniswap V3 / hedge

В предыдущем ДЗ рассматривалась LP-стратегия с хеджем в логике Uniswap V3. Этот проект показал, что concentrated liquidity сильно зависит от выбора диапазона и правил ребалансировки.

Что берём:

- структуру исторического backtest;
- идею анализа рыночных режимов;
- Monte Carlo stress tests;
- общую hedge-логику.

Что меняем:

- в финальном проекте используется Uniswap V2, а не V3;
- Uniswap V2 выбран потому, что его LP exposure проще формализовать и защитить в mini whitepaper.

## 3. Aave EDA

В EDA по Aave были рассмотрены данные по lending/borrowing markets, utilization, APY и активности протокола.

Что берём:

- обоснование выбора Aave V3 как инструмента хеджирования;
- анализ ставок заимствования и доходности collateral;
- обсуждение WETH borrow и USDC collateral;
- описание источников данных.

Что не выносим в центр проекта:

- динамику цены токена AAVE;
- treasury / collector activity;
- длинное сравнение Aave с другими lending-протоколами.
