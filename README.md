# DeFi LP Aave Hedge — Data Pipeline

Этот архив содержит research/data pipeline для проекта **Aave-хеджированная Uniswap V2 ETH/USDC LP-стратегия**.

Пайплайн делает три вещи:

1. Загружает данные по рынку:
   - ETH/USDC price;
   - Uniswap V2 WETH/USDC TVL, volume, fees, liquidity;
   - Aave V3 WETH borrow rate;
   - Aave V3 USDC supply rate.
2. Собирает единый файл `data/processed/market_data.csv`.
3. Валидирует данные через pytest-тесты и simple quality checks.

## Важно про ключи

В архиве **нет приватных ключей и реальных API keys**. Используется `.env.example` с плейсхолдерами.

Не коммитьте в репозиторий:

- `PRIVATE_KEY`;
- реальные Infura / Alchemy keys;
- реальные The Graph / CoinGecko / Dune keys;
- `.env`.

Если приватный ключ уже был отправлен в чат или попал в публичное место, его лучше считать скомпрометированным и заменить.

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Заполните `.env`, затем:

```bash
python scripts/download_data.py --start 2025-01-01 --end 2025-12-31 --frequency hourly
python scripts/build_dataset.py --frequency hourly
python scripts/validate_data.py
pytest -q
```

Если hourly data недоступны или источники возвращают неполные данные:

```bash
python scripts/download_data.py --start 2025-01-01 --end 2025-12-31 --frequency daily
python scripts/build_dataset.py --frequency daily
python scripts/validate_data.py
```

## Основной выходной файл

```text
 data/processed/market_data.csv
```

Обязательные колонки:

```text
timestamp
eth_price_usdc
uni_tvl_usd
uni_volume_usd
uni_fees_usd
uni_liquidity
aave_weth_borrow_rate
aave_usdc_supply_rate
gas_cost_usdc
regime
```

## Архитектура

```text
research/data_pipeline/
├── config.py
├── download_uniswap.py
├── download_aave.py
├── download_prices.py
├── build_dataset.py
├── clean.py
├── regimes.py
└── validate.py
```

`strategy/` и `contracts/` намеренно не включены в этот архив. Этот пакет готовит данные и тесты для последующей реализации стратегий и контрактов.
