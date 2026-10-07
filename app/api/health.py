"""Health-check endpoint."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import Settings


class HealthResponse(BaseModel):
    """Response returned when the service is reachable."""

    status: str
    environment: str
    version: str


def create_health_router(settings: Settings) -> APIRouter:
    """Create a health router bound to the application's settings."""

    health_router = APIRouter(tags=["health"])

    @health_router.get("/health", response_model=HealthResponse, summary="Service health check")
    def health_check() -> HealthResponse:
        """Report that the HTTP service is running."""
        return HealthResponse(
            status="ok",
            environment=settings.environment,
            version=settings.app_version,
        )

    return health_router
