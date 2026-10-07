"""Persistence model for an uploaded source file."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.feature import GeospatialFeature


class UploadedFile(Base):
    """Metadata and processing state for one uploaded geospatial file."""

    __tablename__ = "uploaded_files"
    __table_args__ = (
        CheckConstraint(
            "file_type IN ('kml', 'shapefile_zip')", name="ck_uploaded_files_file_type"
        ),
        CheckConstraint(
            "status IN ('processing', 'ready', 'failed')", name="ck_uploaded_files_status"
        ),
        CheckConstraint("size_bytes >= 0", name="ck_uploaded_files_size_bytes_nonnegative"),
        CheckConstraint("feature_count >= 0", name="ck_uploaded_files_feature_count_nonnegative"),
        CheckConstraint("char_length(sha256) = 64", name="ck_uploaded_files_sha256_length"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="processing")
    source_crs: Mapped[str | None] = mapped_column(String(255))
    feature_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_code: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    features: Mapped[list[GeospatialFeature]] = relationship(
        back_populates="uploaded_file",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="GeospatialFeature.feature_index",
    )
