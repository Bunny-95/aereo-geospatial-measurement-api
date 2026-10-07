"""Create the initial PostGIS persistence schema.

Revision ID: 20261007_0001
Revises: None
Create Date: 2026-10-07 00:00:00
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20261007_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create upload and feature metadata tables with PostGIS support."""
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "uploaded_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="processing", nullable=False),
        sa.Column("source_crs", sa.String(length=255), nullable=True),
        sa.Column("feature_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "file_type IN ('kml', 'shapefile_zip')", name="ck_uploaded_files_file_type"
        ),
        sa.CheckConstraint(
            "status IN ('processing', 'ready', 'failed')", name="ck_uploaded_files_status"
        ),
        sa.CheckConstraint("size_bytes >= 0", name="ck_uploaded_files_size_bytes_nonnegative"),
        sa.CheckConstraint(
            "feature_count >= 0", name="ck_uploaded_files_feature_count_nonnegative"
        ),
        sa.CheckConstraint("char_length(sha256) = 64", name="ck_uploaded_files_sha256_length"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_table(
        "geospatial_features",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feature_index", sa.Integer(), nullable=False),
        sa.Column("source_feature_id", sa.String(length=512), nullable=True),
        sa.Column("geometry_type", sa.String(length=64), nullable=False),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(geometry_type="GEOMETRY", srid=-1, spatial_index=False),
            nullable=True,
        ),
        sa.Column("source_crs", sa.String(length=255), nullable=True),
        sa.Column(
            "properties",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("measurement_type", sa.String(length=32), nullable=True),
        sa.Column("measurement_value", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("measurement_unit", sa.String(length=32), nullable=True),
        sa.Column("measurement_crs", sa.String(length=255), nullable=True),
        sa.Column(
            "measurement_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint("feature_index >= 0", name="ck_geospatial_features_index_nonnegative"),
        sa.ForeignKeyConstraint(["file_id"], ["uploaded_files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_id", "feature_index", name="uq_geospatial_features_file_index"),
    )
    op.create_index(
        "ix_geospatial_features_file_id", "geospatial_features", ["file_id"], unique=False
    )
    op.create_index(
        "ix_geospatial_features_geometry_gist",
        "geospatial_features",
        ["geometry"],
        unique=False,
        postgresql_using="gist",
    )


def downgrade() -> None:
    """Drop the application tables while retaining the shared PostGIS extension."""
    op.drop_index("ix_geospatial_features_geometry_gist", table_name="geospatial_features")
    op.drop_index("ix_geospatial_features_file_id", table_name="geospatial_features")
    op.drop_table("geospatial_features")
    op.drop_table("uploaded_files")
