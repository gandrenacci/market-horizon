"""Transparent financial metric calculations."""

from dataclasses import dataclass
from datetime import date
from math import sqrt

import numpy as np
import pandas as pd

from market_horizon.asset_types import is_continuous


@dataclass(frozen=True)
class TrendSnapshot:
    """Trend classification for one horizon."""

    label: str
    moving_average_name: str
    moving_average_value: float | None
    price_distance: float | None
    performance: float | None
    explanation: str


@dataclass(frozen=True)
class MetricsSnapshot:
    """Latest analytics for an asset."""

    latest_date: date | None
    latest_price: float | None
    daily_change: float | None
    daily_return: float | None
    one_month_return: float | None
    three_month_return: float | None
    ytd_return: float | None
    one_year_return: float | None
    three_year_return: float | None
    ema_20: float | None
    sma_50: float | None
    sma_200: float | None
    rsi_14: float | None
    volatility_30: float | None
    volatility_90: float | None
    drawdown_52w: float | None
    max_drawdown: float | None
    low_52w: float | None
    high_52w: float | None
    range_position_52w: float | None
    short_trend: TrendSnapshot
    medium_trend: TrendSnapshot
    long_trend: TrendSnapshot


def compute_metrics(
    prices: pd.DataFrame,
    *,
    asset_type: str,
    stock_annualization_factor: int = 252,
    crypto_annualization_factor: int = 365,
) -> MetricsSnapshot:
    """Compute the latest metric snapshot for daily OHLCV data."""

    close = _price_series(prices)
    if close.empty:
        unavailable = _unavailable_trend("EMA 20")
        return MetricsSnapshot(
            latest_date=None,
            latest_price=None,
            daily_change=None,
            daily_return=None,
            one_month_return=None,
            three_month_return=None,
            ytd_return=None,
            one_year_return=None,
            three_year_return=None,
            ema_20=None,
            sma_50=None,
            sma_200=None,
            rsi_14=None,
            volatility_30=None,
            volatility_90=None,
            drawdown_52w=None,
            max_drawdown=None,
            low_52w=None,
            high_52w=None,
            range_position_52w=None,
            short_trend=unavailable,
            medium_trend=_unavailable_trend("SMA 50"),
            long_trend=_unavailable_trend("SMA 200"),
        )

    returns = close.pct_change()
    ema_20_series = close.ewm(span=20, adjust=False, min_periods=20).mean()
    sma_50_series = close.rolling(50, min_periods=50).mean()
    sma_200_series = close.rolling(200, min_periods=200).mean()
    annualization = (
        crypto_annualization_factor if is_continuous(asset_type) else stock_annualization_factor
    )
    latest_date = close.index[-1]
    latest_price = _last_float(close)
    daily_change = _daily_change(close)
    one_month = _period_return(close, 21)
    three_month = _period_return(close, 63)
    one_year = _period_return(close, 252)
    three_year = _period_return(close, 756)
    low_52w, high_52w, range_pos = _range_52w(close)

    return MetricsSnapshot(
        latest_date=latest_date,
        latest_price=latest_price,
        daily_change=daily_change,
        daily_return=_period_return(close, 1),
        one_month_return=one_month,
        three_month_return=three_month,
        ytd_return=_ytd_return(close),
        one_year_return=one_year,
        three_year_return=three_year,
        ema_20=_last_valid_float(ema_20_series),
        sma_50=_last_valid_float(sma_50_series),
        sma_200=_last_valid_float(sma_200_series),
        rsi_14=_last_valid_float(_rsi(close, 14)),
        volatility_30=_rolling_volatility(returns, 30, annualization),
        volatility_90=_rolling_volatility(returns, 90, annualization),
        drawdown_52w=_drawdown_52w(close),
        max_drawdown=_max_drawdown(close),
        low_52w=low_52w,
        high_52w=high_52w,
        range_position_52w=range_pos,
        short_trend=_trend(close, ema_20_series, "EMA 20", one_month),
        medium_trend=_trend(close, sma_50_series, "SMA 50", three_month),
        long_trend=_trend(close, sma_200_series, "SMA 200", one_year),
    )


def add_indicators(prices: pd.DataFrame) -> pd.DataFrame:
    """Return a chart-ready frame with price and moving averages."""

    frame = prices.copy()
    close = _price_series(frame)
    frame["price"] = close
    frame["ema_20"] = close.ewm(span=20, adjust=False, min_periods=20).mean()
    frame["sma_50"] = close.rolling(50, min_periods=50).mean()
    frame["sma_200"] = close.rolling(200, min_periods=200).mean()
    return frame


def normalized_performance(prices_by_symbol: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Normalize multiple price histories to zero percent at the first shared observation."""

    series = {
        symbol: _price_series(frame).rename(symbol) for symbol, frame in prices_by_symbol.items()
    }
    if not series:
        return pd.DataFrame()
    aligned = pd.concat(series.values(), axis=1).sort_index().ffill().dropna(how="any")
    if aligned.empty:
        return aligned
    return aligned.divide(aligned.iloc[0]).subtract(1.0)


def _price_series(prices: pd.DataFrame) -> pd.Series:
    if prices.empty:
        return pd.Series(dtype=float)
    column = "adj_close" if "adj_close" in prices.columns else "close"
    series = prices[column].dropna().astype(float)
    if not isinstance(series.index, pd.DatetimeIndex):
        series.index = pd.to_datetime(series.index).date
    return series


def _period_return(close: pd.Series, periods: int) -> float | None:
    if len(close) <= periods:
        return None
    base = close.iloc[-periods - 1]
    latest = close.iloc[-1]
    if base == 0:
        return None
    return float(latest / base - 1.0)


def _ytd_return(close: pd.Series) -> float | None:
    latest_date = close.index[-1]
    year_start = date(latest_date.year, 1, 1)
    ytd = close[close.index >= year_start]
    if len(ytd) < 2 or ytd.iloc[0] == 0:
        return None
    return float(ytd.iloc[-1] / ytd.iloc[0] - 1.0)


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period, min_periods=period).mean()
    avg_loss = loss.rolling(period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(100.0).where(avg_gain.notna())


def _rolling_volatility(returns: pd.Series, window: int, annualization: int) -> float | None:
    if returns.dropna().shape[0] < window:
        return None
    value = returns.rolling(window, min_periods=window).std().iloc[-1]
    return None if pd.isna(value) else float(value * sqrt(annualization))


def _drawdown_52w(close: pd.Series) -> float | None:
    if len(close) < 2:
        return None
    window = close.tail(min(252, len(close)))
    high = window.max()
    if high == 0:
        return None
    return float(close.iloc[-1] / high - 1.0)


def _max_drawdown(close: pd.Series) -> float | None:
    if len(close) < 2:
        return None
    drawdowns = close / close.cummax() - 1.0
    return float(drawdowns.min())


def _range_52w(close: pd.Series) -> tuple[float | None, float | None, float | None]:
    if close.empty:
        return None, None, None
    window = close.tail(min(252, len(close)))
    low = float(window.min())
    high = float(window.max())
    if high == low:
        return low, high, None
    return low, high, float((close.iloc[-1] - low) / (high - low))


def _trend(
    close: pd.Series,
    average: pd.Series,
    average_name: str,
    performance: float | None,
) -> TrendSnapshot:
    average_value = _last_valid_float(average)
    latest_price = _last_float(close)
    if (
        average_value is None
        or latest_price is None
        or performance is None
        or average.dropna().shape[0] < 2
    ):
        return _unavailable_trend(average_name)
    previous_average = float(average.dropna().iloc[-2])
    distance = latest_price / average_value - 1.0 if average_value else None
    rising = average_value > previous_average
    if latest_price > average_value and rising and performance > 0:
        label = "Positive"
    elif latest_price < average_value and not rising and performance < 0:
        label = "Negative"
    else:
        label = "Mixed"
    direction = "rising" if rising else "falling"
    relation = "above" if latest_price >= average_value else "below"
    explanation = f"Price is {relation} {average_name}, and {average_name} is {direction}."
    return TrendSnapshot(label, average_name, average_value, distance, performance, explanation)


def _unavailable_trend(average_name: str) -> TrendSnapshot:
    return TrendSnapshot(
        label="Unavailable",
        moving_average_name=average_name,
        moving_average_value=None,
        price_distance=None,
        performance=None,
        explanation="Not enough stored history for this horizon.",
    )


def _last_float(series: pd.Series) -> float | None:
    if series.empty or pd.isna(series.iloc[-1]):
        return None
    return float(series.iloc[-1])


def _last_valid_float(series: pd.Series) -> float | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return float(valid.iloc[-1])


def _daily_change(close: pd.Series) -> float | None:
    if len(close) < 2:
        return None
    return float(close.iloc[-1] - close.iloc[-2])
