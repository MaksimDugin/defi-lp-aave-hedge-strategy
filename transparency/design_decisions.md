# Зафиксированные проектные решения

## Тип проекта

Проект оформляется как DeFi vault strategy с воспроизводимым историческим backtest.

## Основная стратегия

Стратегия предоставляет ликвидность в Uniswap V2 ETH/USDC и частично хеджирует ETH exposure LP-позиции через заём WETH в Aave V3.

## Распределение капитала

Начальный капитал делится следующим образом:

- 50% капитала направляется в Uniswap V2 ETH/USDC LP;
- 50% капитала используется как collateral / hedge reserve в Aave V3.

## Хедж

Borrowed WETH считается реальной short ETH exposure. Мы предполагаем, что после займа WETH продаётся в USDC.

Базовый hedge ratio:

- 75% от ETH-delta LP-позиции.

Для sensitivity analysis:

- 50%;
- 75%.

## Ребалансировка

Хедж ребалансируется, когда отклонение между целевым WETH debt и текущим WETH debt превышает заданный threshold.

Базовый threshold:

- 10%.

## Риск-менеджмент

Стратегия отслеживает:

- Aave health factor;
- LTV;
- borrow funding cost;
- gas costs;
- slippage;
- idle tokens;
- circuit breaker events.

## Baselines

Стратегия сравнивается с:

1. Buy & Hold 50/50 ETH/USDC;
2. plain Uniswap V2 ETH/USDC LP;
3. LP с fixed initial hedge.

## Основная гипотеза

Стратегия должна улучшить результат plain Uniswap V2 LP за счёт снижения направленной ETH exposure при сохранении дохода от AMM-комиссий.

## Использование LLM

LLM используется для структурирования, черновиков текста и scaffolding кода. Финальные допущения, параметры, интерпретация данных и выводы проверяются авторами проекта вручную.
