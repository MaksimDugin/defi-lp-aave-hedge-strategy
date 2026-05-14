from research.data_pipeline.build_dataset import build_market_dataset
from research.data_pipeline.config import build_config

config = build_config(
    start="2025-01-01",
    end="2025-12-31",
    frequency="hourly",
)

df = build_market_dataset(config)

print("Dataset built successfully.")
print("Saved to:", config.processed_market_data_path)
print("Rows:", len(df))