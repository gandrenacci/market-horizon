"""Application configuration."""

import os
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from defaults, optional config file, .env, and env vars."""

    model_config = SettingsConfigDict(
        env_prefix="MARKET_HORIZON_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_data_dir: Path = Field(default_factory=lambda: Path.home() / ".market_horizon")
    database_path: Path | None = None
    default_data_provider: str = "yfinance"
    initial_history_period: str = "3y"
    sync_overlap_days: int = 7
    default_benchmark: str = "^GSPC"
    log_level: str = "INFO"
    stock_annualization_factor: int = 252
    crypto_annualization_factor: int = 365

    @computed_field  # type: ignore[prop-decorator]
    @property
    def resolved_database_path(self) -> Path:
        """Return the configured SQLite path or the default inside the app data directory."""

        return self.database_path or self.app_data_dir / "market_horizon.db"


def _read_config_file() -> dict[str, Any]:
    config_path = Path(os.environ.get("MARKET_HORIZON_CONFIG_FILE", "market_horizon.toml"))
    if not config_path.exists():
        return {}
    with config_path.open("rb") as fh:
        data = tomllib.load(fh)
    section = data.get("market_horizon", data)
    if not isinstance(section, dict):
        return {}
    return section


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """Load settings with environment variables overriding the optional TOML file."""

    file_values = _read_config_file()
    settings = Settings(**file_values)
    settings.app_data_dir.mkdir(parents=True, exist_ok=True)
    settings.resolved_database_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
