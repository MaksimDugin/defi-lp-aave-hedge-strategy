1. Проект делаем как DeFi vault strategy.
2. Главный deliverable — reproducible GitHub repo.
3. Старый Solidity vault используем как prototype.
4. Capital allocation = 50% LP / 50% Aave collateral.
5. Hedge = partial, 50–75%.
6. Base hedge ratio = 75%.
7. Borrowed WETH считаем как настоящий short через продажу в USDC.
8. Historical backtest + Monte Carlo stress tests.
9. Main claim: strategy improves plain LP.
10. Но финальный вывод честный: если PnL не лучше, анализируем trade-off.
