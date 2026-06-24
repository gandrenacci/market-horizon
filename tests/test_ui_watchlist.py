from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np
import pandas as pd

from market_horizon.ui.app import (
    _WL_SORTABLE,
    _momentum_card_html,
    _sort_table,
    _watchlist_table,
)


def _prices(length: int, start: float = 100.0, step: float = 1.0) -> pd.DataFrame:
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(length)]
    values = np.array([start + i * step for i in range(length)], dtype=float)
    return pd.DataFrame(
        {
            "open": values,
            "high": values + 1,
            "low": values - 1,
            "close": values,
            "adj_close": values,
            "volume": 1000,
        },
        index=dates,
    )


def _make_table() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Symbol": ["BBB", "AAA", "CCC"],
            "_Price": [20.0, 10.0, float("nan")],
            "_1D": [0.05, -0.02, 0.01],
            "_1M": [0.0, 0.0, 0.0],
            "_1Y": [0.0, 0.0, 0.0],
            "_3Y": [0.0, 0.0, 0.0],
            "_Volatility": [0.0, 0.0, 0.0],
        }
    )


def test_sort_table_numeric_descending_puts_nan_last() -> None:
    sorted_table = _sort_table(_make_table(), "price", ascending=False)

    assert list(sorted_table["Symbol"]) == ["BBB", "AAA", "CCC"]


def test_sort_table_numeric_ascending_puts_nan_last() -> None:
    sorted_table = _sort_table(_make_table(), "price", ascending=True)

    assert list(sorted_table["Symbol"]) == ["AAA", "BBB", "CCC"]


def test_sort_table_by_symbol() -> None:
    sorted_table = _sort_table(_make_table(), "symbol", ascending=True)

    assert list(sorted_table["Symbol"]) == ["AAA", "BBB", "CCC"]


def test_sort_table_drops_hidden_columns() -> None:
    sorted_table = _sort_table(_make_table(), "1d", ascending=True)

    assert not any(column.startswith("_") for column in sorted_table.columns)


def test_sortable_map_covers_requested_columns() -> None:
    assert set(_WL_SORTABLE) == {"symbol", "price", "1d", "1m", "1y", "3y", "volatility"}


def test_watchlist_table_exposes_every_sort_key() -> None:
    asset = SimpleNamespace(id=1, symbol="AAA", name="Alpha", asset_type="Stock", currency="USD")
    repository = SimpleNamespace(
        latest_sync_for_symbols=lambda symbols: {},
        load_prices=lambda asset_id: _prices(300),
    )
    settings = SimpleNamespace(
        stock_annualization_factor=252,
        crypto_annualization_factor=365,
    )

    table = _watchlist_table(repository, settings, [asset])  # type: ignore[arg-type]

    for _, sort_key in _WL_SORTABLE.values():
        assert sort_key in table.columns


def test_momentum_card_unavailable_has_no_bar() -> None:
    html = _momentum_card_html(None)

    assert "Unavailable" in html
    assert "mh-rsi-bar" not in html


def test_momentum_card_renders_value_and_fill() -> None:
    html = _momentum_card_html(58.3)

    assert "58.30" in html
    assert "width:58.3%" in html
