# Research data pipeline

Эта папка отвечает за сбор, очистку, синхронизацию и проверку данных для backtest.

Основной результат:

```text
data/processed/market_data.csv
```

Файл используется engineering-частью для:

- `fractal-defi` backtest;
- baseline comparison;
- Monte Carlo calibration;
- графиков и таблиц результатов.
