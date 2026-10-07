"""File-upload metadata endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import UploadValidationError
from app.db.models import GeospatialFeature, UploadedFile
from app.db.session import get_db_session
from app.schemas.file import (
    FileMeasurementsResponse,
    MeasurementResponse,
    UploadedFileResponse,
)
from app.services.ingestion import UploadIngestionService
from app.storage.local import LocalStorage


def create_files_router(settings: Settings) -> APIRouter:
    """Create the upload routes using configured local storage."""
    router = APIRouter(prefix="/api/files", tags=["files"])
    ingestion_service = UploadIngestionService(settings, LocalStorage(settings.upload_directory))

    @router.post("/", response_model=UploadedFileResponse, status_code=status.HTTP_201_CREATED)
    def upload_file(
        file: Annotated[UploadFile, File(...)],
        session: Annotated[Session, Depends(get_db_session)],
    ) -> UploadedFile:
        """Validate and persist a KML or Shapefile ZIP in processing state."""
        try:
            return ingestion_service.ingest(
                stream=file.file,
                filename=file.filename,
                content_type=file.content_type,
                session=session,
            )
        except UploadValidationError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
            ) from error

    @router.get("/{file_id}", response_model=UploadedFileResponse)
    def get_uploaded_file(
        file_id: UUID,
        session: Annotated[Session, Depends(get_db_session)],
    ) -> UploadedFile:
        """Return safe metadata for one uploaded file."""
        uploaded_file = session.get(UploadedFile, file_id)
        if uploaded_file is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found.",
            )
        return uploaded_file

    @router.get("/{file_id}/measurements/", response_model=FileMeasurementsResponse)
    def get_file_measurements(
        file_id: UUID,
        session: Annotated[Session, Depends(get_db_session)],
    ) -> FileMeasurementsResponse:
        """Return measurements calculated for all features in an uploaded file."""

        uploaded_file = session.get(UploadedFile, file_id)

        if uploaded_file is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found.",
            )

        if uploaded_file.status == "processing":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="File processing is still in progress.",
            )

        if uploaded_file.status == "failed":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=uploaded_file.error_message or "File processing failed.",
            )

        features = (
            session.query(GeospatialFeature)
            .filter(GeospatialFeature.file_id == file_id)
            .order_by(GeospatialFeature.feature_index)
            .all()
        )

        measurements = [
            MeasurementResponse(
                feature_index=feature.feature_index,
                geometry_type=feature.geometry_type,
                measurement_type=feature.measurement_type or "unsupported",
                value=(
                    float(feature.measurement_value)
                    if feature.measurement_value is not None
                    else None
                ),
                unit=feature.measurement_unit,
                calculation_crs=feature.measurement_crs,
            )
            for feature in features
        ]

        return FileMeasurementsResponse(
            file_id=uploaded_file.id,
            status=uploaded_file.status,
            measurements=measurements,
        )

    return router
