"""Yahoo Finance provider implementation."""

from datetime import date
from typing import Any

import pandas as pd
import yfinance as yf

from market_horizon.asset_types import classify
from market_horizon.data.provider import AssetMetadata, PriceFrame


class YFinanceProvider:
    """Market data provider backed by yfinance."""

    def get_metadata(self, symbol: str) -> AssetMetadata:
        normalized = normalize_symbol(symbol)
        ticker = yf.Ticker(normalized)
        history = ticker.history(period="5d", interval="1d", auto_adjust=False)
        if history.empty:
            raise ValueError(f"No historical data found for {normalized}.")
        info: dict[str, Any] = ticker.get_info() or {}
        return AssetMetadata(
            symbol=normalized,
            name=info.get("longName") or info.get("shortName"),
            asset_type=classify(normalized, info.get("quoteType")),
            currency=info.get("currency"),
            exchange=info.get("exchange") or info.get("fullExchangeName"),
        )

    def get_history(
        self,
        symbol: str,
        *,
        period: str | None = None,
        start: date | None = None,
    ) -> PriceFrame:
        normalized = normalize_symbol(symbol)
        ticker = yf.Ticker(normalized)
        kwargs: dict[str, Any] = {"interval": "1d", "auto_adjust": False}
        if start is not None:
            kwargs["start"] = start.isoformat()
        else:
            kwargs["period"] = period or "3y"
        frame = ticker.history(**kwargs)
        if frame.empty:
            raise ValueError(f"No historical data found for {normalized}.")
        frame = frame.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Adj Close": "adj_close",
                "Volume": "volume",
            }
        )
        expected = ["open", "high", "low", "close", "adj_close", "volume"]
        for column in expected:
            if column not in frame.columns:
                frame[column] = None
        frame = frame[expected].copy()
        frame.index = pd.to_datetime(frame.index).tz_localize(None).date
        frame.index.name = "date"
        return frame.dropna(how="all", subset=["open", "high", "low", "close", "adj_close"])


def normalize_symbol(symbol: str) -> str:
    """Normalize user-entered ticker symbols for Yahoo Finance."""

    return symbol.strip().upper()
