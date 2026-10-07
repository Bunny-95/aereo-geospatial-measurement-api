"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.health import create_health_router
from app.api.routes.files import create_files_router
from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    runtime_settings = settings or get_settings()

    application = FastAPI(
        title=runtime_settings.app_name,
        version=runtime_settings.app_version,
        debug=runtime_settings.debug,
    )
    application.include_router(create_health_router(runtime_settings))
    application.include_router(create_files_router(runtime_settings))
    return application


app = create_app()
