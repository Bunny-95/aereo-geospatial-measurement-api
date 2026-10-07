"""Integration tests for the Phase 3 file-upload API."""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path
from uuid import uuid4

import pytest
from app.core.config import Settings
from app.db.models import UploadedFile
from app.db.session import get_db_session
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session


def shapefile_zip(entries: dict[str, bytes] | None = None) -> bytes:
    """Return a small ZIP with the minimum expected Shapefile components."""
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        for name, content in (entries or valid_shapefile_entries()).items():
            archive.writestr(name, content)
    return archive_bytes.getvalue()


def valid_shapefile_entries() -> dict[str, bytes]:
    """Return non-geospatial placeholder members for archive-structure validation."""
    return {
        "dataset/boundary.shp": b"shape",
        "dataset/boundary.shx": b"index",
        "dataset/boundary.dbf": b"attributes",
    }


@pytest.fixture
def client(tmp_path: Path, db_session: Session) -> TestClient:
    """Provide the API with isolated storage and a transaction-isolated database session."""
    settings = Settings(
        environment="test",
        upload_directory=tmp_path / "uploads",
        max_upload_size_bytes=1024,
        max_zip_uncompressed_size_bytes=2048,
    )
    app = create_app(settings)
    app.dependency_overrides[get_db_session] = lambda: db_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def upload(client: TestClient, filename: str, content: bytes) -> object:
    """Send one multipart upload to the actual endpoint."""
    return client.post("/api/files/", files={"file": (filename, content)})


def test_upload_valid_kml_creates_ready_record(
    client: TestClient,
    db_session: Session,
) -> None:
    """A valid KML upload is parsed and processed immediately."""
    content = b"""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>
            <Placemark>
                <name>Test Area</name>
                <Polygon>
                    <outerBoundaryIs>
                        <LinearRing>
                            <coordinates>
                                77.5946,12.9716,0
                                77.5956,12.9716,0
                                77.5956,12.9726,0
                                77.5946,12.9726,0
                                77.5946,12.9716,0
                            </coordinates>
                        </LinearRing>
                    </outerBoundaryIs>
                </Polygon>
            </Placemark>
        </Document>
    </kml>
    """

    response = upload(client, "boundary.kml", content)

    assert response.status_code == 201
    payload = response.json()
    print(payload)

    assert payload["status"] == "ready"
    assert payload["file_type"] == "kml"
    assert payload["feature_count"] == 1
    assert payload["source_crs"] is not None
    assert payload["sha256"] == hashlib.sha256(content).hexdigest()

    assert db_session.get(UploadedFile, payload["id"]).original_filename == "boundary.kml"


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("boundary.geojson", b"{}"),
        ("empty.kml", b""),
    ],
)
def test_invalid_uploads_create_no_database_record(
    client: TestClient, db_session: Session, filename: str, content: bytes
) -> None:
    """Unsupported and empty uploads are rejected before metadata is created."""
    response = upload(client, filename, content)

    assert response.status_code == 422
    assert db_session.scalars(select(UploadedFile)).all() == []


def test_oversized_upload_is_rejected_without_orphan(client: TestClient, tmp_path: Path) -> None:
    """Chunked storage rejects a file beyond the configured maximum and removes it."""
    response = upload(client, "oversized.kml", b"x" * 1025)

    assert response.status_code == 422
    assert list((tmp_path / "uploads").rglob("*")) == [tmp_path / "uploads" / "uploads"]


@pytest.mark.parametrize(
    "entries",
    [
        {"../escape.shp": b"x", "../escape.shx": b"x", "../escape.dbf": b"x"},
        {"notes.txt": b"not a Shapefile"},
        {"boundary.shp": b"x", "boundary.dbf": b"x"},
    ],
)
def test_unsafe_or_invalid_archives_are_rejected(
    client: TestClient, entries: dict[str, bytes]
) -> None:
    """ZIP inspection rejects traversal and incomplete/non-Shapefile archives without extraction."""
    response = upload(client, "boundary.zip", shapefile_zip(entries))

    assert response.status_code == 422


def test_zip_decompressed_size_limit_is_enforced(client: TestClient) -> None:
    """Archive member sizes are capped before any future extraction stage."""
    entries = valid_shapefile_entries()
    entries["dataset/boundary.dbf"] = b"x" * 2049

    response = upload(client, "boundary.zip", shapefile_zip(entries))

    assert response.status_code == 422


def test_uploaded_file_metadata_can_be_retrieved(client: TestClient) -> None:
    """GET returns the persisted public metadata for an uploaded file."""
    created = upload(client, "boundary.kml", b"<kml/>")

    response = client.get(f"/api/files/{created.json()['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created.json()["id"]


def test_unknown_uploaded_file_returns_not_found(client: TestClient) -> None:
    """GET returns 404 rather than exposing database implementation details."""
    response = client.get(f"/api/files/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "File not found."}



def test_measurements_endpoint_returns_polygon_area(
    client: TestClient,
) -> None:
    """GET measurements returns the calculated area for a polygon feature."""
    content = b"""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>
            <Placemark>
                <name>Test Area</name>
                <Polygon>
                    <outerBoundaryIs>
                        <LinearRing>
                            <coordinates>
                                77.5946,12.9716,0
                                77.5956,12.9716,0
                                77.5956,12.9726,0
                                77.5946,12.9726,0
                                77.5946,12.9716,0
                            </coordinates>
                        </LinearRing>
                    </outerBoundaryIs>
                </Polygon>
            </Placemark>
        </Document>
    </kml>
    """

    created = upload(client, "boundary.kml", content)
    assert created.status_code == 201

    file_id = created.json()["id"]

    response = client.get(f"/api/files/{file_id}/measurements/")

    assert response.status_code == 200

    payload = response.json()

    assert payload["file_id"] == file_id
    assert payload["status"] == "ready"
    assert len(payload["measurements"]) == 1

    measurement = payload["measurements"][0]

    assert measurement["feature_index"] == 0
    assert measurement["geometry_type"] == "Polygon"
    assert measurement["measurement_type"] == "area"
    assert measurement["value"] is not None
    assert measurement["value"] > 0
    assert measurement["unit"] == "square_meters"
    assert measurement["calculation_crs"].startswith("EPSG:")


def test_measurements_endpoint_handles_point(client: TestClient) -> None:
    
    content = b"""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>
            <Placemark>
                <name>Test Point</name>
                <Point>
                    <coordinates>77.5946,12.9716,0</coordinates>
                </Point>
            </Placemark>
        </Document>
    </kml>
    """

    created = upload(client, "point.kml", content)
    assert created.status_code == 201

    file_id = created.json()["id"]

    response = client.get(f"/api/files/{file_id}/measurements/")

    assert response.status_code == 200

    measurement = response.json()["measurements"][0]

    assert measurement["geometry_type"] == "Point"
    assert measurement["measurement_type"] == "not_applicable"
    assert measurement["value"] is None
    assert measurement["unit"] is None
    assert measurement["calculation_crs"] is None


def test_unknown_file_measurements_returns_not_found(client: TestClient) -> None:
    """Measurements endpoint returns 404 for an unknown file."""
    response = client.get(f"/api/files/{uuid4()}/measurements/")

    assert response.status_code == 404
    assert response.json() == {"detail": "File not found."}