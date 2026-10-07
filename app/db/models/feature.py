"""Persistence model for a parsed geospatial feature."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from geoalchemy2 import Geometry
from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.uploaded_file import UploadedFile


class GeospatialFeature(Base):
    """A source feature and any later measurement derived from it."""

    __tablename__ = "geospatial_features"
    __table_args__ = (
        UniqueConstraint("file_id", "feature_index", name="uq_geospatial_features_file_index"),
        CheckConstraint("feature_index >= 0", name="ck_geospatial_features_index_nonnegative"),
        Index("ix_geospatial_features_geometry_gist", "geometry", postgresql_using="gist"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    file_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("uploaded_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_index: Mapped[int] = mapped_column(Integer, nullable=False)
    source_feature_id: Mapped[str | None] = mapped_column(String(512))
    geometry_type: Mapped[str] = mapped_column(String(64), nullable=False)
    geometry: Mapped[Any | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=-1, spatial_index=False), nullable=True
    )
    source_crs: Mapped[str | None] = mapped_column(Text)
    properties: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    measurement_type: Mapped[str | None] = mapped_column(String(32))
    measurement_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    measurement_unit: Mapped[str | None] = mapped_column(String(32))
    measurement_crs: Mapped[str | None] = mapped_column(Text)
    measurement_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    uploaded_file: Mapped[UploadedFile] = relationship(back_populates="features")
