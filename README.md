# Market Horizon

Market Horizon is a local-first dashboard for monitoring stocks, ETFs, and cryptocurrencies.
It downloads daily OHLCV data through Yahoo Finance, stores it in SQLite, and presents
performance, trend, momentum, and risk metrics across short, medium, and long horizons.

This project is informational only. It does not provide trading recommendations, forecasts,
broker integration, alerts, or portfolio accounting.

## Quick Start

```bash
uv sync
cp .env.example .env
uv run streamlit run app.py
```

On first startup, the app creates the local SQLite database and a default watchlist. The
watchlist starts empty and the UI asks for initial symbols such as:

```text
AAPL, CSSX5E.MI, BTC-EUR
```

For Yahoo Finance cryptocurrency pairs, use symbols like `BTC-EUR` or `ETH-EUR`.

## Configuration

Configuration is loaded from built-in defaults, an optional `market_horizon.toml` file,
`.env`, and environment variables.

```bash
cp .env.example .env
```

Useful environment variables:

```text
MARKET_HORIZON_APP_DATA_DIR=.data
MARKET_HORIZON_DATABASE_PATH=.data/market_horizon.db
MARKET_HORIZON_INITIAL_HISTORY_PERIOD=3y
MARKET_HORIZON_SYNC_OVERLAP_DAYS=7
MARKET_HORIZON_DEFAULT_BENCHMARK=^GSPC
```

## Database Migration

```bash
uv run alembic upgrade head
```

The app also creates the schema automatically on startup for local convenience.

## Tests and Quality

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

Optional Git hooks (lint, format, secret scanning) are configured in `.pre-commit-config.yaml`:

```bash
pre-commit install
pre-commit run --all-files
```

## Docker

```bash
docker compose up --build
```

The app will be available at <http://localhost:8501>.

## Scope

The MVP includes:

- Watchlist management with add, remove, filter, sort, sync-all, and per-asset refresh.
- Daily OHLCV storage in SQLite without synthetic weekend or holiday rows.
- Incremental sync with a seven-calendar-day overlap.
- Independent ticker sync failures with visible status.
- Asset detail analysis with a momentum panel (daily, 1M, 3M, YTD, 1Y, and 3Y returns),
  EMA 20, SMA 50, SMA 200, RSI 14, 30/90-day volatility, drawdowns, and 52-week range metrics.
- Normalized comparison for two to five assets.
- A Learn page with plain-language explanations of every metric.

Market data may be delayed, incomplete, corrected later by the provider, or temporarily
unavailable.

## License

Licensed under the [Apache License 2.0](LICENSE). See [`SECURITY.md`](SECURITY.md) for
vulnerability reporting and [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) for community expectations.

