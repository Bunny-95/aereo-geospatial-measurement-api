"""Synchronous SQLAlchemy engine and session utilities."""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings


def create_database_engine(settings: Settings) -> Engine:
    """Create a synchronous PostgreSQL engine for the provided settings."""
    return create_engine(settings.database_url, echo=settings.database_echo, pool_pre_ping=True)


engine = create_database_engine(get_settings())
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    """Yield a request-scoped database session and always close it."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def database_is_available(database_engine: Engine = engine) -> bool:
    """Return whether a lightweight query can reach the database."""
    try:
        with database_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return False
    return True
