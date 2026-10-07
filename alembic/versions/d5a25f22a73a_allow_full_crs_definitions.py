"""allow full CRS definitions

Revision ID: d5a25f22a73a
Revises: 20261007_0001
Create Date: 2026-10-07 16:05:00.640689

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5a25f22a73a"
down_revision: str | Sequence[str] | None = "20261007_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "uploaded_files",
        "source_crs",
        existing_type=sa.VARCHAR(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )

    op.alter_column(
        "geospatial_features",
        "source_crs",
        existing_type=sa.VARCHAR(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )

    op.alter_column(
        "geospatial_features",
        "measurement_crs",
        existing_type=sa.VARCHAR(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "uploaded_files",
        "source_crs",
        existing_type=sa.Text(),
        type_=sa.VARCHAR(length=255),
        existing_nullable=True,
    )

    op.alter_column(
        "geospatial_features",
        "source_crs",
        existing_type=sa.Text(),
        type_=sa.VARCHAR(length=255),
        existing_nullable=True,
    )

    op.alter_column(
        "geospatial_features",
        "measurement_crs",
        existing_type=sa.Text(),
        type_=sa.VARCHAR(length=255),
        existing_nullable=True,
    )
