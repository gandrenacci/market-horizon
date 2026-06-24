"""Repository layer for local market data."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from market_horizon.data.provider import AssetMetadata
from market_horizon.db.models import (
    Asset,
    DailyPrice,
    SyncResult,
    SyncRun,
    Watchlist,
    WatchlistEntry,
)


@dataclass(frozen=True)
class UpsertCounts:
    """Inserted and updated row counts."""

    inserted: int
    updated: int


class MarketRepository:
    """Persistence operations for assets, prices, watchlists, and sync status."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get_default_watchlist(self) -> Watchlist:
        with self._session_factory() as session:
            watchlist = session.scalar(select(Watchlist).where(Watchlist.name == "Default"))
            if watchlist is None:
                watchlist = Watchlist(name="Default")
                session.add(watchlist)
                session.commit()
            return watchlist

    def list_watchlist_assets(self) -> list[Asset]:
        with self._session_factory() as session:
            stmt = (
                select(Asset)
                .join(WatchlistEntry, WatchlistEntry.asset_id == Asset.id)
                .join(Watchlist, Watchlist.id == WatchlistEntry.watchlist_id)
                .where(Watchlist.name == "Default")
                .order_by(Asset.symbol)
            )
            return list(session.scalars(stmt).all())

    def get_asset_by_symbol(self, symbol: str) -> Asset | None:
        with self._session_factory() as session:
            return session.scalar(select(Asset).where(Asset.symbol == symbol))

    def upsert_asset(self, metadata: AssetMetadata) -> Asset:
        with self._session_factory() as session:
            asset = session.scalar(select(Asset).where(Asset.symbol == metadata.symbol))
            if asset is None:
                asset = Asset(
                    symbol=metadata.symbol,
                    name=metadata.name,
                    asset_type=metadata.asset_type,
                    currency=metadata.currency,
                    exchange=metadata.exchange,
                )
                session.add(asset)
            else:
                asset.name = metadata.name
                asset.asset_type = metadata.asset_type
                asset.currency = metadata.currency
                asset.exchange = metadata.exchange
            session.commit()
            return asset

    def add_to_default_watchlist(self, asset_id: int) -> bool:
        with self._session_factory() as session:
            watchlist = session.scalar(select(Watchlist).where(Watchlist.name == "Default"))
            if watchlist is None:
                watchlist = Watchlist(name="Default")
                session.add(watchlist)
                session.flush()
            existing = session.scalar(
                select(WatchlistEntry).where(
                    WatchlistEntry.watchlist_id == watchlist.id,
                    WatchlistEntry.asset_id == asset_id,
                )
            )
            if existing is not None:
                return False
            session.add(WatchlistEntry(watchlist_id=watchlist.id, asset_id=asset_id))
            session.commit()
            return True

    def remove_from_default_watchlist(self, symbol: str) -> bool:
        with self._session_factory() as session:
            stmt = (
                select(WatchlistEntry)
                .join(Asset, Asset.id == WatchlistEntry.asset_id)
                .join(Watchlist, Watchlist.id == WatchlistEntry.watchlist_id)
                .where(Asset.symbol == symbol, Watchlist.name == "Default")
            )
            entry = session.scalar(stmt)
            if entry is None:
                return False
            session.delete(entry)
            session.commit()
            return True

    def latest_price_date(self, asset_id: int) -> date | None:
        with self._session_factory() as session:
            return session.scalar(
                select(func.max(DailyPrice.date)).where(DailyPrice.asset_id == asset_id)
            )

    def upsert_prices(self, asset_id: int, prices: pd.DataFrame) -> UpsertCounts:
        inserted = 0
        updated = 0
        with self._session_factory() as session:
            for price_date, row in prices.iterrows():
                existing = session.scalar(
                    select(DailyPrice).where(
                        DailyPrice.asset_id == asset_id,
                        DailyPrice.date == price_date,
                    )
                )
                values = {
                    "open": _none_or_float(row.get("open")),
                    "high": _none_or_float(row.get("high")),
                    "low": _none_or_float(row.get("low")),
                    "close": _none_or_float(row.get("close")),
                    "adj_close": _none_or_float(row.get("adj_close") or row.get("close")),
                    "volume": _none_or_float(row.get("volume")),
                }
                if existing is None:
                    session.add(DailyPrice(asset_id=asset_id, date=price_date, **values))
                    inserted += 1
                else:
                    for key, value in values.items():
                        setattr(existing, key, value)
                    updated += 1
            session.commit()
        return UpsertCounts(inserted=inserted, updated=updated)

    def load_prices(self, asset_id: int) -> pd.DataFrame:
        with self._session_factory() as session:
            rows = session.scalars(
                select(DailyPrice).where(DailyPrice.asset_id == asset_id).order_by(DailyPrice.date)
            ).all()
        records = [
            {
                "date": row.date,
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
                "adj_close": row.adj_close,
                "volume": row.volume,
            }
            for row in rows
        ]
        if not records:
            return pd.DataFrame(columns=["open", "high", "low", "close", "adj_close", "volume"])
        return pd.DataFrame.from_records(records).set_index("date")

    def create_sync_run(self) -> int:
        with self._session_factory() as session:
            run = SyncRun()
            session.add(run)
            session.commit()
            return run.id

    def finish_sync_run(self, run_id: int, status: str, duration_seconds: float) -> None:
        with self._session_factory() as session:
            run = session.get(SyncRun, run_id)
            if run is not None:
                run.status = status
                run.finished_at = datetime.now(UTC)
                run.duration_seconds = duration_seconds
                session.commit()

    def add_sync_result(
        self,
        *,
        run_id: int | None,
        asset_id: int | None,
        symbol: str,
        status: str,
        reason: str | None,
        inserted_rows: int,
        updated_rows: int,
        duration_seconds: float,
        latest_date: date | None,
    ) -> None:
        with self._session_factory() as session:
            session.add(
                SyncResult(
                    run_id=run_id,
                    asset_id=asset_id,
                    symbol=symbol,
                    status=status,
                    reason=reason,
                    inserted_rows=inserted_rows,
                    updated_rows=updated_rows,
                    duration_seconds=duration_seconds,
                    latest_date=latest_date,
                )
            )
            session.commit()

    def latest_sync_for_symbols(self, symbols: Iterable[str]) -> dict[str, SyncResult]:
        with self._session_factory() as session:
            results: dict[str, SyncResult] = {}
            for symbol in symbols:
                result = session.scalar(
                    select(SyncResult)
                    .where(SyncResult.symbol == symbol, SyncResult.status == "success")
                    .order_by(SyncResult.created_at.desc(), SyncResult.id.desc())
                    .limit(1)
                )
                if result is not None:
                    results[symbol] = result
            return results


def _none_or_float(value: Any) -> float | None:
    if pd.isna(value):
        return None
    return float(value)
