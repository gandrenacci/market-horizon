from datetime import date, timedelta

import numpy as np
import pandas as pd

from market_horizon.analytics.metrics import add_indicators, compute_metrics, normalized_performance


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


def test_metrics_calculate_core_values_for_enough_history() -> None:
    metrics = compute_metrics(_prices(300), asset_type="Stock")

    assert metrics.latest_price == 399.0
    assert metrics.daily_return is not None
    assert metrics.one_month_return is not None
    assert metrics.one_year_return is not None
    assert metrics.three_year_return is None
    assert metrics.ema_20 is not None
    assert metrics.sma_50 is not None
    assert metrics.sma_200 is not None
    assert metrics.rsi_14 is not None
    assert metrics.volatility_30 is not None
    assert metrics.drawdown_52w == 0.0
    assert metrics.max_drawdown == 0.0
    assert metrics.range_position_52w == 1.0
    assert metrics.short_trend.label == "Positive"
    assert metrics.medium_trend.label == "Positive"
    assert metrics.long_trend.label == "Positive"


def test_metrics_three_year_return_available_with_long_history() -> None:
    metrics = compute_metrics(_prices(800), asset_type="Stock")

    assert metrics.three_year_return is not None


def test_metrics_return_unavailable_for_missing_history() -> None:
    metrics = compute_metrics(_prices(10), asset_type="ETF")

    assert metrics.one_month_return is None
    assert metrics.ema_20 is None
    assert metrics.short_trend.label == "Unavailable"
    assert metrics.medium_trend.label == "Unavailable"
    assert metrics.long_trend.label == "Unavailable"


def test_metrics_return_unavailable_for_empty_prices() -> None:
    metrics = compute_metrics(pd.DataFrame(), asset_type="Stock")

    assert metrics.latest_date is None
    assert metrics.latest_price is None
    assert metrics.short_trend.label == "Unavailable"


def test_crypto_volatility_uses_365_day_annualization() -> None:
    prices = _prices(120, step=2.0)
    stock = compute_metrics(prices, asset_type="Stock")
    crypto = compute_metrics(prices, asset_type="Cryptocurrency")

    assert stock.volatility_30 is not None
    assert crypto.volatility_30 is not None
    assert crypto.volatility_30 > stock.volatility_30


def test_add_indicators_returns_chart_ready_columns() -> None:
    frame = add_indicators(_prices(220))

    assert {"price", "ema_20", "sma_50", "sma_200"}.issubset(frame.columns)
    assert frame["sma_200"].dropna().iloc[-1] > 0


def test_normalized_performance_aligns_and_forward_fills_display_data() -> None:
    left = _prices(5)
    right = _prices(5, start=50.0, step=2.0).drop(index=date(2024, 1, 3))

    normalized = normalized_performance({"AAA": left, "BBB": right})

    assert list(normalized.columns) == ["AAA", "BBB"]
    assert normalized.iloc[0].to_dict() == {"AAA": 0.0, "BBB": 0.0}
    assert not normalized.isna().any().any()


def test_normalized_performance_handles_empty_inputs() -> None:
    assert normalized_performance({}).empty
    assert normalized_performance({"EMPTY": pd.DataFrame()}).empty


def test_metrics_use_close_when_adjusted_close_is_absent() -> None:
    prices = _prices(40).drop(columns=["adj_close"])

    metrics = compute_metrics(prices, asset_type="Stock")

    assert metrics.latest_price == 139.0


def test_metrics_handle_zero_bases_and_flat_ranges() -> None:
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(40)]
    zero_base = pd.DataFrame(
        {"close": [0.0] + [10.0] * 39, "adj_close": [0.0] + [10.0] * 39},
        index=dates,
    )
    flat = pd.DataFrame({"close": [10.0] * 40, "adj_close": [10.0] * 40}, index=dates)

    zero_metrics = compute_metrics(zero_base, asset_type="Stock")
    flat_metrics = compute_metrics(flat, asset_type="Stock")

    assert zero_metrics.ytd_return is None
    assert flat_metrics.range_position_52w is None


def test_metrics_classify_negative_and_mixed_trends() -> None:
    negative = compute_metrics(_prices(300, start=500.0, step=-1.0), asset_type="Stock")
    mixed_prices = _prices(300)
    mixed_prices.iloc[-1, mixed_prices.columns.get_loc("adj_close")] = 385.0
    mixed_prices.iloc[-1, mixed_prices.columns.get_loc("close")] = 385.0

    mixed = compute_metrics(mixed_prices, asset_type="Stock")

    assert negative.short_trend.label == "Negative"
    assert mixed.short_trend.label == "Mixed"


def test_metrics_short_series_risk_values_are_unavailable() -> None:
    metrics = compute_metrics(_prices(1), asset_type="Stock")

    assert metrics.daily_change is None
    assert metrics.drawdown_52w is None
    assert metrics.max_drawdown is None
