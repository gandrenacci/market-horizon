# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Market Horizon is a local-first Streamlit dashboard for monitoring stocks, ETFs, funds, indices,
crypto, FX pairs, and futures. It downloads daily OHLCV data from Yahoo Finance (`yfinance`),
stores it in local SQLite, and renders
performance, trend, momentum, and risk metrics across short/medium/long horizons. It is
informational only — no trading signals, forecasts, broker integration, alerts, or portfolio
accounting. The Streamlit UI has four pages — Watchlist, Asset Analysis, Compare, and Learn.

## Commands

`uv` manages the environment and runs everything; always invoke tools via `uv run`.

```bash
uv sync                          # install deps from lockfile (use --all-groups for dev tools)
uv run streamlit run app.py      # start the dashboard (http://localhost:8501)
uv run alembic upgrade head      # apply schema migrations (also auto-created on startup)
uv run pytest                    # full test suite (coverage is on by default via pyproject)
uv run pytest tests/test_analytics_metrics.py::test_name   # single test
uv run ruff check .              # lint
uv run ruff format --check .     # formatting check
uv run mypy src                  # strict type check (src only)
docker compose up --build        # run in Docker
```

CI (`.github/workflows/ci.yml`) has two jobs: a `test` job running, in order, ruff check, ruff
format check, mypy, pytest, and `docker compose build`; and a `secret-scanning` job (Gitleaks).
Match the test sequence locally before pushing. mypy runs in `strict` mode. Local Git hooks are
pinned in `.pre-commit-config.yaml` — install with `pre-commit install`, run with
`pre-commit run --all-files`.

## Architecture

Layered with dependency injection; the dependency direction is one-way:
`ui → services → {data provider, repository} → db`. Analytics, config, and `asset_types` are leaf
modules.

- **`asset_types.py`** — Single source of truth for the canonical asset taxonomy (`Stock`, `ETF`,
  `Fund`, `Index`, `Cryptocurrency`, `Forex`, `Future`). `classify(symbol, quote_type)` applies
  symbol-shape rules first — `^…` → Index, `…=F` → Future, `…=X` → Forex — because Yahoo mislabels
  those as `EQUITY`/empty, then trusts `quoteType`, falling back to "hyphenated ⇒ Crypto, else Stock"
  only when `quoteType` is missing (so `BRK-B` stays a stock). Also owns the UI pill label/CSS map,
  the `FILTER_OPTIONS` chip map, and `is_continuous` (the 365-vs-252 volatility switch). Provider,
  analytics, and UI all import from here — never re-hardcode type strings.
- **`data/provider.py`** — `MarketDataProvider` is a `Protocol` (structural typing). Real impl is
  `data/yfinance_provider.py`; tests inject a `FakeProvider` that satisfies the same shape. Any new
  provider just needs `get_metadata` and `get_history`. `get_metadata` sets `asset_type` via
  `asset_types.classify`. `get_history` must return a DataFrame indexed by `date` with normalized
  lower-case columns `open, high, low, close, adj_close, volume`.
- **`db/repository.py`** — `MarketRepository` is the only place that touches the DB. It takes a
  `sessionmaker` and opens a fresh session per method. `upsert_prices` deduplicates on
  `(asset_id, date)`; `_none_or_float` falls back `adj_close → close`.
- **`services/sync.py`** — `SyncService` orchestrates provider + repository. Key invariant:
  **a single ticker's failure must never abort the batch.** `sync_asset` catches all exceptions and
  records a `failed` `TickerSyncResult` instead of raising. Incremental sync re-requests from
  `latest_price_date - sync_overlap_days` (default 7) so the provider can correct recent data;
  initial sync uses `initial_history_period` (default `3y`). Non-initial syncs also do a
  best-effort `_refresh_metadata` (re-`upsert_asset`) so a stored asset is re-classified when the
  rules change — a metadata failure is swallowed and never fails the price sync.
- **`analytics/metrics.py`** — Pure functions over a price DataFrame; no I/O. `compute_metrics`
  returns a frozen `MetricsSnapshot`. **Insufficient history yields `None` / `"Unavailable"`, never
  a misleading value** — preserve this when editing. Uses `adj_close` when present, else `close`.
  Volatility annualization is asset-type dependent via `asset_types.is_continuous`: 365 for crypto,
  252 for everything else.
- **`config/settings.py`** — `Settings` (pydantic-settings). Precedence: env vars > optional
  `market_horizon.toml` > defaults. Env vars use the `MARKET_HORIZON_` prefix. `load_settings()` is
  `lru_cache`d and creates data dirs as a side effect. The DB path is `resolved_database_path`.
- **`ui/app.py`** — All Streamlit UI in one module. `_bootstrap()` is `@st.cache_resource` and wires
  settings → session factory → repository → provider → sync service once per server. Heavy inline
  CSS in `_inject_styles`. Watchlist tables carry hidden `_`-prefixed columns for sorting/search
  that are stripped before display. Runtime assets — the page banner, browser-tab logo, and the
  Learn-page explanations markdown — load from `assets/` (`_ASSETS_DIR`) behind `.is_file()` guards,
  so the UI degrades gracefully if a file is missing.

## Conventions

- Keep financial calculations transparent and deterministic. Do not add hidden trading signals,
  hardcoded personal tickers, portfolio quantities, or notebook-specific code.
- Do not commit secrets, personal watchlists, the local SQLite DB, or `.env` (provide `.env.example`).
- Migrations: `Base.metadata` is the migration target, but the app also calls `init_db` to
  `create_all` on startup for local convenience — keep Alembic migrations and `db/models.py` in sync.
- Tests live in `tests/`, named `test_<area>_<aspect>.py`, and inject fakes rather than hitting the
  network. Target ≥95% coverage on analytics and ≥80% overall (MVP acceptance criteria).
- Python 3.12+; ruff line length 100; type hints on public functions.
