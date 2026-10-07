"""PostgreSQL/PostGIS persistence integration tests."""

from uuid import uuid4

import pytest
from app.db.models import GeospatialFeature, UploadedFile
from app.db.session import database_is_available
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def make_uploaded_file(**overrides: object) -> UploadedFile:
    """Build a valid uploaded file model for persistence tests."""
    values: dict[str, object] = {
        "original_filename": "boundary.kml",
        "file_type": "kml",
        "content_type": "application/vnd.google-earth.kml+xml",
        "size_bytes": 128,
        "sha256": "a" * 64,
        "storage_key": f"uploads/{uuid4()}/boundary.kml",
    }
    values.update(overrides)
    return UploadedFile(**values)


def test_database_connection(database_engine) -> None:
    """The configured PostgreSQL service accepts a basic connection."""
    assert database_is_available(database_engine)
    with database_engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1


def test_model_tables_are_created(database_engine, db_session: Session) -> None:
    """ORM metadata creates both persistence tables and the spatial index."""
    inspector = inspect(database_engine)
    assert {"uploaded_files", "geospatial_features"}.issubset(inspector.get_table_names())
    assert any(
        index["name"] == "ix_geospatial_features_geometry_gist"
        for index in inspector.get_indexes("geospatial_features")
    )


def test_file_feature_relationship_persists(db_session: Session) -> None:
    """A feature belongs to one upload and is available through the relationship."""
    uploaded_file = make_uploaded_file()
    feature = GeospatialFeature(
        feature_index=0,
        geometry_type="Point",
        properties={"name": "sample"},
        uploaded_file=uploaded_file,
    )
    db_session.add(feature)
    db_session.commit()

    persisted_file = db_session.get(UploadedFile, uploaded_file.id)
    assert persisted_file is not None
    assert persisted_file.features == [feature]
    assert feature.file_id == uploaded_file.id


def test_feature_unique_index_constraint_is_enforced(db_session: Session) -> None:
    """A source feature index cannot be repeated within the same upload."""
    uploaded_file = make_uploaded_file()
    db_session.add(uploaded_file)
    db_session.flush()
    db_session.add_all(
        [
            GeospatialFeature(file_id=uploaded_file.id, feature_index=0, geometry_type="Point"),
            GeospatialFeature(file_id=uploaded_file.id, feature_index=0, geometry_type="Point"),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_feature_foreign_key_constraint_is_enforced(db_session: Session) -> None:
    """A feature cannot reference an upload that does not exist."""
    db_session.add(GeospatialFeature(file_id=uuid4(), feature_index=0, geometry_type="Point"))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
