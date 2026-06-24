"""SQLAlchemy session helpers."""

from collections.abc import Callable
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from market_horizon.db.models import Base, Watchlist


def create_engine_for_path(database_path: Path) -> Engine:
    """Create a SQLite engine for the configured database path.

    ``check_same_thread=False`` is required because the engine is cached once and
    shared across Streamlit script-runner threads; without it, a pooled connection
    reused on another thread raises ``ProgrammingError``.
    """

    return create_engine(
        f"sqlite:///{database_path}",
        future=True,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )


def create_session_factory(database_path: Path) -> sessionmaker[Session]:
    """Create a SQLAlchemy session factory."""

    engine = create_engine_for_path(database_path)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_db(session_factory: Callable[[], Session]) -> None:
    """Create schema and default watchlist if they do not exist."""

    engine = session_factory.kw["bind"] if hasattr(session_factory, "kw") else None
    if engine is None:
        with session_factory() as session:
            engine = session.get_bind()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        default = session.query(Watchlist).filter_by(name="Default").one_or_none()
        if default is None:
            session.add(Watchlist(name="Default"))
            session.commit()
