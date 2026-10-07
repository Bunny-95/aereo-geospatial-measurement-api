"""Public schemas for uploaded file metadata."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UploadedFileResponse(BaseModel):
    """Safe uploaded-file metadata returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    file_type: str
    content_type: str | None
    size_bytes: int
    sha256: str
    status: str
    source_crs: str | None
    feature_count: int
    error_code: str | None
    error_message: str | None
    created_at: datetime
    processed_at: datetime | None


class MeasurementResponse(BaseModel):
    """Measurement details for one geospatial feature."""

    feature_index: int
    geometry_type: str
    measurement_type: str
    value: float | None
    unit: str | None
    calculation_crs: str | None


class FileMeasurementsResponse(BaseModel):
    """Measurements calculated for all features in an uploaded file."""

    file_id: UUID
    status: str
    measurements: list[MeasurementResponse]
