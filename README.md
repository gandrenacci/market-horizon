# Market Horizon

Market Horizon is a local-first dashboard for monitoring stocks, ETFs, funds, indices,
cryptocurrencies, FX pairs, and futures. It downloads daily OHLCV data through Yahoo Finance,
stores it in SQLite, and presents performance, trend, momentum, and risk metrics across short,
medium, and long horizons.

![Market Horizon overview](assets/market-horizon.gif)

## Philosophy

Market Horizon is built to **monitor assets over the long term, not to encourage trading**. The
goal is a minimalist dashboard that surfaces a few essential — but meaningful — short-, medium-,
and long-term indicators, rather than overwhelming you with noise that invites frequent buying and
selling. It is paired with a financial-education page that explains the basic concepts and every
indicator used, so the numbers are understood rather than just consumed.

This project is informational only. It does not provide trading recommendations, forecasts,
broker integration, alerts, or portfolio accounting.

## Quick Start

```bash
uv sync
cp .env.example .env
uv run streamlit run app.py
```

On first startup, the app creates the local SQLite database and a default watchlist. The
watchlist starts empty and the UI asks for initial symbols. A good mixed starter set that
exercises every asset type is:

```text
QQQM, BTC-USD, GC=F, NFLX, ^IXIC, ^GSPC
```

For Yahoo Finance cryptocurrency pairs, use symbols like `BTC-USD` or `ETH-EUR`.

## Asset Types

Yahoo Finance is inconsistent about instrument classification — it often reports
`quoteType = EQUITY` (or nothing) for indices, FX pairs, and futures. Market Horizon
normalizes everything into a small, stable taxonomy in `src/market_horizon/asset_types.py`,
so the metrics, filters, and UI stay consistent regardless of provider quirks.

| Type             | Example symbols          | How it is detected                                   |
| ---------------- | ------------------------ | ---------------------------------------------------- |
| `Index`          | `^IXIC`, `^GSPC`         | Symbol starts with `^` (or `quoteType = index`)      |
| `Future`         | `GC=F`, `ES=F`           | Symbol ends with `=F` (or `quoteType = future`)      |
| `Forex`          | `EURUSD=X`               | Symbol ends with `=X` (or `quoteType = currency`)    |
| `ETF`            | `QQQM`, `VOO`            | `quoteType = etf`                                    |
| `Fund`           | `VTSAX`, `VFIAX`         | `quoteType = mutualfund`                             |
| `Cryptocurrency` | `BTC-USD`, `ETH-EUR`     | `quoteType = cryptocurrency`, or a hyphenated symbol |
| `Stock`          | `NFLX`, `AAPL`, `BRK-B`  | `quoteType = equity`, and the default fallback       |

Symbol-shape rules (`^`, `=F`, `=X`) take precedence because Yahoo mislabels those
instruments; `quoteType` is trusted for everything else. The stored classification is
refreshed on every sync, so existing assets are re-classified automatically after a
**Sync all** or **Refresh** when the rules change.

## Configuration

Configuration is loaded from built-in defaults, an optional `market_horizon.toml` file,
`.env`, and environment variables.

```bash
cp .env.example .env                            # environment-variable config
cp market_horizon.toml.example market_horizon.toml   # optional TOML config
```

The real `.env` and `market_horizon.toml` are gitignored; commit only the `*.example` files.

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

> [!WARNING]
> The container ships with **no authentication** and binds to `0.0.0.0`. It is intended for local
> or trusted-network use only. Do **not** publish port `8501` directly to the Internet — anyone who
> reaches it could edit the watchlist and drive traffic to Yahoo Finance. Place it behind a reverse
> proxy that provides authentication and TLS if remote access is required.

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

