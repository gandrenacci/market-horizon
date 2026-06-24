"""Provider interfaces for market data."""

from dataclasses import dataclass
from datetime import date
from typing import Protocol

import pandas as pd

type PriceFrame = pd.DataFrame


@dataclass(frozen=True)
class AssetMetadata:
    """Provider metadata for a tradable asset."""

    symbol: str
    name: str | None
    asset_type: str
    currency: str | None
    exchange: str | None


class MarketDataProvider(Protocol):
    """Protocol implemented by market data providers."""

    def get_metadata(self, symbol: str) -> AssetMetadata:
        """Return provider metadata or raise ValueError for invalid symbols."""

    def get_history(
        self,
        symbol: str,
        *,
        period: str | None = None,
        start: date | None = None,
    ) -> PriceFrame:
        """Return daily OHLCV history with normalized lower-case columns."""
