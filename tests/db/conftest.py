"""Fixtures for PostgreSQL/PostGIS integration tests."""

from collections.abc import Generator

import pytest
from app.core.config import Settings
from app.db.models import GeospatialFeature, UploadedFile  # noqa: F401
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session


@pytest.fixture(scope="session")
def database_engine() -> Generator[Engine, None, None]:
    """Provide the configured database engine or skip if Docker is not running."""
    engine = create_engine(Settings().database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip(
            "PostgreSQL is unavailable; start Docker Compose to run database integration tests."
        )

    yield engine
    engine.dispose()


@pytest.fixture
def db_session(database_engine: Engine) -> Generator[Session, None, None]:
    """Provide a transaction-isolated session against the migrated schema."""
    connection = database_engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
