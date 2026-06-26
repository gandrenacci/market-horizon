from datetime import date

import pandas as pd
import pytest

from market_horizon.asset_types import classify
from market_horizon.config import Settings
from market_horizon.data.provider import AssetMetadata
from market_horizon.db import create_session_factory, init_db
from market_horizon.db.repository import MarketRepository
from market_horizon.services.sync import SyncService


class FakeProvider:
    def __init__(self, fail_symbols: set[str] | None = None) -> None:
        self.fail_symbols = fail_symbols or set()
        self.starts: list[date | None] = []

    def get_metadata(self, symbol: str) -> AssetMetadata:
        normalized = symbol.strip().upper()
        if normalized in self.fail_symbols:
            raise ValueError("invalid symbol")
        asset_type = classify(normalized, None)
        return AssetMetadata(normalized, f"{normalized} Name", asset_type, "USD", "TEST")

    def get_history(
        self,
        symbol: str,
        *,
        period: str | None = None,
        start: date | None = None,
    ) -> pd.DataFrame:
        del period
        normalized = symbol.strip().upper()
        self.starts.append(start)
        if normalized in self.fail_symbols:
            raise RuntimeError("provider unavailable")
        dates = [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)]
        return pd.DataFrame(
            {
                "open": [10, 11, 12],
                "high": [11, 12, 13],
                "low": [9, 10, 11],
                "close": [10, 11, 12],
                "adj_close": [10, 11, 12],
                "volume": [100, 110, 120],
            },
            index=dates,
        )


@pytest.fixture
def repository(tmp_path) -> MarketRepository:  # type: ignore[no-untyped-def]
    session_factory = create_session_factory(tmp_path / "test.db")
    init_db(session_factory)
    return MarketRepository(session_factory)


def test_add_symbol_creates_watchlist_entry_and_upserts_prices(
    repository: MarketRepository,
) -> None:
    service = SyncService(
        provider=FakeProvider(),
        repository=repository,
        settings=Settings(app_data_dir=".", database_path=":memory:"),
    )

    result = service.add_symbol("aapl")

    assert result.status == "success"
    assert result.inserted_rows == 3
    assert [asset.symbol for asset in repository.list_watchlist_assets()] == ["AAPL"]
    asset = repository.list_watchlist_assets()[0]
    assert len(repository.load_prices(asset.id)) == 3


def test_add_symbol_unavailable_returns_failed_without_raising(
    repository: MarketRepository,
) -> None:
    service = SyncService(
        provider=FakeProvider(fail_symbols={"ARB-EUR"}),
        repository=repository,
        settings=Settings(app_data_dir=".", database_path=":memory:"),
    )

    result = service.add_symbol("ARB-EUR")

    assert result.status == "failed"
    assert result.reason == "invalid symbol"
    assert result.symbol == "ARB-EUR"
    assert repository.list_watchlist_assets() == []


def test_re_adding_existing_symbol_skips_initial_redownload(
    repository: MarketRepository,
) -> None:
    provider = FakeProvider()
    service = SyncService(
        provider=provider,
        repository=repository,
        settings=Settings(app_data_dir=".", database_path=":memory:"),
    )
    service.add_symbol("AAPL")
    downloads_after_first_add = len(provider.starts)

    result = service.add_symbol("AAPL")

    assert result.status == "skipped"
    assert result.reason == "Already in watchlist."
    assert result.inserted_rows == 0
    # No additional history download was triggered by the duplicate add.
    assert len(provider.starts) == downloads_after_first_add
    assert [asset.symbol for asset in repository.list_watchlist_assets()] == ["AAPL"]


def test_incremental_sync_uses_overlap_and_updates_existing_rows(
    repository: MarketRepository,
) -> None:
    provider = FakeProvider()
    service = SyncService(
        provider=provider,
        repository=repository,
        settings=Settings(app_data_dir=".", database_path=":memory:", sync_overlap_days=7),
    )
    service.add_symbol("AAPL")
    asset = repository.list_watchlist_assets()[0]

    result = service.sync_asset(asset, initial=False, run_id=None)

    assert result.status == "success"
    assert result.updated_rows == 3
    assert provider.starts[-1] == date(2023, 12, 27)


def test_sync_refreshes_stale_asset_classification(
    repository: MarketRepository,
) -> None:
    provider = FakeProvider()
    service = SyncService(
        provider=provider,
        repository=repository,
        settings=Settings(app_data_dir=".", database_path=":memory:"),
    )
    # An index added before the classification fix is stored as a stock.
    repository.upsert_asset(AssetMetadata("^GSPC", "S&P 500", "Stock", "USD", "TEST"))
    asset = repository.get_asset_by_symbol("^GSPC")
    assert asset is not None
    repository.add_to_default_watchlist(asset.id)

    service.sync_asset(asset, initial=False, run_id=None)

    refreshed = repository.get_asset_by_symbol("^GSPC")
    assert refreshed is not None
    assert refreshed.asset_type == "Index"


def test_sync_all_reports_partial_failures(repository: MarketRepository) -> None:
    provider = FakeProvider()
    service = SyncService(
        provider=provider,
        repository=repository,
        settings=Settings(app_data_dir=".", database_path=":memory:"),
    )
    service.add_symbol("AAPL")
    repository.upsert_asset(AssetMetadata("FAIL", "Failure", "Stock", "USD", "TEST"))
    fail_asset = repository.get_asset_by_symbol("FAIL")
    assert fail_asset is not None
    repository.add_to_default_watchlist(fail_asset.id)
    provider.fail_symbols.add("FAIL")

    results = service.sync_all(repository.list_watchlist_assets())

    assert {result.symbol: result.status for result in results} == {
        "AAPL": "success",
        "FAIL": "failed",
    }
