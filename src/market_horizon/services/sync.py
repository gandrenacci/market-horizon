"""Market data synchronization service."""

from dataclasses import dataclass
from datetime import date, timedelta
from time import perf_counter

from market_horizon.config import Settings
from market_horizon.data.provider import MarketDataProvider
from market_horizon.db.models import Asset
from market_horizon.db.repository import MarketRepository


@dataclass(frozen=True)
class TickerSyncResult:
    """Result for one ticker synchronization."""

    symbol: str
    status: str
    reason: str | None
    inserted_rows: int
    updated_rows: int
    duration_seconds: float
    latest_date: date | None


class SyncService:
    """Coordinates provider downloads and local persistence."""

    def __init__(
        self,
        *,
        provider: MarketDataProvider,
        repository: MarketRepository,
        settings: Settings,
    ) -> None:
        self._provider = provider
        self._repository = repository
        self._settings = settings

    def add_symbol(self, symbol: str) -> TickerSyncResult:
        """Validate a ticker, add it to the watchlist, and download initial history.

        Re-adding a symbol that is already in the watchlist and already has stored
        history is a no-op: it does not re-download the full history (FR-003).
        """

        started = perf_counter()
        try:
            metadata = self._provider.get_metadata(symbol)
            asset = self._repository.upsert_asset(metadata)
        except Exception as exc:  # noqa: BLE001 - one bad ticker must not abort the batch.
            return TickerSyncResult(
                symbol=symbol,
                status="failed",
                reason=str(exc),
                inserted_rows=0,
                updated_rows=0,
                duration_seconds=perf_counter() - started,
                latest_date=None,
            )
        added = self._repository.add_to_default_watchlist(asset.id)
        if not added and self._repository.latest_price_date(asset.id) is not None:
            return TickerSyncResult(
                symbol=asset.symbol,
                status="skipped",
                reason="Already in watchlist.",
                inserted_rows=0,
                updated_rows=0,
                duration_seconds=0.0,
                latest_date=self._repository.latest_price_date(asset.id),
            )
        return self.sync_asset(asset, initial=True, run_id=None)

    def sync_all(self, assets: list[Asset]) -> list[TickerSyncResult]:
        """Synchronize all assets independently."""

        started = perf_counter()
        run_id = self._repository.create_sync_run()
        results = [self.sync_asset(asset, initial=False, run_id=run_id) for asset in assets]
        status = (
            "success"
            if all(result.status == "success" for result in results)
            else "partial_failure"
        )
        self._repository.finish_sync_run(run_id, status, perf_counter() - started)
        return results

    def sync_asset(
        self,
        asset: Asset,
        *,
        initial: bool,
        run_id: int | None,
    ) -> TickerSyncResult:
        """Synchronize a single asset without raising provider failures to callers."""

        started = perf_counter()
        if not initial:
            self._refresh_metadata(asset)
        try:
            latest_date = None if initial else self._repository.latest_price_date(asset.id)
            start = (
                latest_date - timedelta(days=self._settings.sync_overlap_days)
                if latest_date is not None
                else None
            )
            history = self._provider.get_history(
                asset.symbol,
                period=self._settings.initial_history_period if start is None else None,
                start=start,
            )
            counts = self._repository.upsert_prices(asset.id, history)
            latest = max(history.index) if not history.empty else latest_date
            result = TickerSyncResult(
                symbol=asset.symbol,
                status="success",
                reason=None,
                inserted_rows=counts.inserted,
                updated_rows=counts.updated,
                duration_seconds=perf_counter() - started,
                latest_date=latest,
            )
        except Exception as exc:  # noqa: BLE001 - provider failures must be isolated.
            result = TickerSyncResult(
                symbol=asset.symbol,
                status="failed",
                reason=str(exc),
                inserted_rows=0,
                updated_rows=0,
                duration_seconds=perf_counter() - started,
                latest_date=self._repository.latest_price_date(asset.id),
            )
        self._repository.add_sync_result(
            run_id=run_id,
            asset_id=asset.id,
            symbol=result.symbol,
            status=result.status,
            reason=result.reason,
            inserted_rows=result.inserted_rows,
            updated_rows=result.updated_rows,
            duration_seconds=result.duration_seconds,
            latest_date=result.latest_date,
        )
        return result

    def _refresh_metadata(self, asset: Asset) -> None:
        """Re-fetch and persist provider metadata (name, asset type, ...) for an asset.

        Keeps a stored asset's classification current when provider/logic changes (e.g. an
        index previously saved as a stock). Best-effort: a metadata failure must never turn
        an otherwise-healthy price sync into a failure, so errors are swallowed here.
        """

        try:
            metadata = self._provider.get_metadata(asset.symbol)
        except Exception:  # noqa: BLE001 - metadata refresh is best-effort.
            return
        self._repository.upsert_asset(metadata)
