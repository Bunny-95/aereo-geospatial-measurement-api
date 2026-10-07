"""Environment-driven application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and an optional .env file."""

    app_name: str = "Aereo Geospatial Measurement API"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"
    database_host: str = "localhost"
    database_port: int = 5433
    database_name: str = "aereo_measurements"
    database_user: str = "aereo"
    database_password: str = "aereo_dev_password"
    database_echo: bool = False
    upload_directory: Path = Path("data/uploads")
    max_upload_size_bytes: int = 10 * 1024 * 1024
    max_zip_uncompressed_size_bytes: int = 50 * 1024 * 1024
    allowed_upload_extensions: tuple[str, ...] = (".kml", ".zip")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """Build the synchronous SQLAlchemy URL from database environment settings."""
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.database_user,
            password=self.database_password,
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
        ).render_as_string(hide_password=False)


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance for the application process."""
    return Settings()
