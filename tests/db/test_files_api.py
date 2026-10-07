"""Integration tests for the file-upload API."""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path
from uuid import uuid4

import fiona
import pytest
from app.core.config import Settings
from app.db.models import UploadedFile
from app.db.session import get_db_session
from app.main import create_app
from fastapi.testclient import TestClient
from shapely.geometry import Polygon, mapping
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
    """Return non-geospatial placeholder members for archive validation."""
    return {
        "dataset/boundary.shp": b"shape",
        "dataset/boundary.shx": b"index",
        "dataset/boundary.dbf": b"attributes",
    }


def real_shapefile_zip(tmp_path: Path) -> bytes:
    """Create a real WGS84 polygon Shapefile and return it as a ZIP archive."""
    shapefile_dir = tmp_path / "shapefile"
    shapefile_dir.mkdir()

    schema = {
        "geometry": "Polygon",
        "properties": {"name": "str:80"},
    }

    shp_path = shapefile_dir / "boundary.shp"

    with fiona.open(
        shp_path,
        mode="w",
        driver="ESRI Shapefile",
        schema=schema,
        crs="EPSG:4326",
    ) as collection:
        polygon = Polygon(
            [
                (77.5946, 12.9716),
                (77.5956, 12.9716),
                (77.5956, 12.9726),
                (77.5946, 12.9726),
                (77.5946, 12.9716),
            ]
        )

        collection.write(
            {
                "geometry": mapping(polygon),
                "properties": {"name": "Test Area"},
            }
        )

    archive_bytes = io.BytesIO()

    with zipfile.ZipFile(archive_bytes, "w") as archive:
        for path in shapefile_dir.iterdir():
            archive.write(path, path.name)

    return archive_bytes.getvalue()


@pytest.fixture
def client(tmp_path: Path, db_session: Session) -> TestClient:
    """Provide the API with isolated storage and a test database session."""
    settings = Settings(
        environment="test",
        upload_directory=tmp_path / "uploads",
        max_upload_size_bytes=16 * 1024,
        max_zip_uncompressed_size_bytes=2048,
    )

    app = create_app(settings)
    app.dependency_overrides[get_db_session] = lambda: db_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def upload(client: TestClient, filename: str, content: bytes):
    """Send one multipart upload to the actual endpoint."""
    return client.post(
        "/api/files/",
        files={"file": (filename, content)},
    )


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

    assert payload["status"] == "ready"
    assert payload["file_type"] == "kml"
    assert payload["feature_count"] == 1
    assert payload["source_crs"] is not None
    assert payload["sha256"] == hashlib.sha256(content).hexdigest()

    uploaded_file = db_session.get(UploadedFile, payload["id"])

    assert uploaded_file is not None
    assert uploaded_file.original_filename == "boundary.kml"


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("boundary.geojson", b"{}"),
        ("empty.kml", b""),
    ],
)
def test_invalid_uploads_create_no_database_record(
    client: TestClient,
    db_session: Session,
    filename: str,
    content: bytes,
) -> None:
    """Unsupported and empty uploads are rejected before metadata is created."""
    response = upload(client, filename, content)

    assert response.status_code == 422
    assert db_session.scalars(select(UploadedFile)).all() == []


def test_oversized_upload_is_rejected_without_orphan(
    client: TestClient,
    tmp_path: Path,
) -> None:
    """Chunked storage rejects a file beyond the configured maximum."""
    response = upload(
        client,
        "oversized.kml",
        b"x" * (16 * 1024 + 1),
    )

    assert response.status_code == 422

    upload_directory = tmp_path / "uploads"

    assert list(upload_directory.rglob("*")) == [upload_directory / "uploads"]


@pytest.mark.parametrize(
    "entries",
    [
        {
            "../escape.shp": b"x",
            "../escape.shx": b"x",
            "../escape.dbf": b"x",
        },
        {
            "notes.txt": b"not a Shapefile",
        },
        {
            "boundary.shp": b"x",
            "boundary.dbf": b"x",
        },
    ],
)
def test_unsafe_or_invalid_archives_are_rejected(
    client: TestClient,
    entries: dict[str, bytes],
) -> None:
    """ZIP inspection rejects traversal and incomplete archives."""
    response = upload(
        client,
        "boundary.zip",
        shapefile_zip(entries),
    )

    assert response.status_code == 422


def test_zip_decompressed_size_limit_is_enforced(
    client: TestClient,
) -> None:
    """Archive member sizes are capped before extraction."""
    entries = valid_shapefile_entries()

    entries["dataset/boundary.dbf"] = b"x" * 2049

    response = upload(
        client,
        "boundary.zip",
        shapefile_zip(entries),
    )

    assert response.status_code == 422


def test_uploaded_file_metadata_can_be_retrieved(
    client: TestClient,
) -> None:
    """GET returns persisted public metadata for an uploaded file."""
    created = upload(
        client,
        "boundary.kml",
        b"<kml/>",
    )

    response = client.get(f"/api/files/{created.json()['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created.json()["id"]


def test_unknown_uploaded_file_returns_not_found(
    client: TestClient,
) -> None:
    """GET returns 404 for an unknown uploaded file."""
    response = client.get(f"/api/files/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "File not found."}


def test_measurements_endpoint_returns_conflict_while_processing(
    client: TestClient,
    db_session: Session,
) -> None:
    """Measurements endpoint returns 409 while processing is still in progress."""
    uploaded_file = UploadedFile(
        original_filename="processing.kml",
        file_type="kml",
        content_type="application/vnd.google-earth.kml+xml",
        size_bytes=10,
        sha256="a" * 64,
        storage_key="processing.kml",
        status="processing",
        feature_count=0,
    )

    db_session.add(uploaded_file)
    db_session.commit()
    db_session.refresh(uploaded_file)

    response = client.get(f"/api/files/{uploaded_file.id}/measurements/")

    assert response.status_code == 409
    assert response.json() == {"detail": "File processing is still in progress."}


def test_measurements_endpoint_returns_unprocessable_for_failed_file(
    client: TestClient,
    db_session: Session,
) -> None:
    """Measurements endpoint returns 422 when processing failed."""
    uploaded_file = UploadedFile(
        original_filename="failed.kml",
        file_type="kml",
        content_type="application/vnd.google-earth.kml+xml",
        size_bytes=10,
        sha256="b" * 64,
        storage_key="failed.kml",
        status="failed",
        feature_count=0,
        error_code="PARSING_ERROR",
        error_message="Unable to parse the uploaded file.",
    )

    db_session.add(uploaded_file)
    db_session.commit()
    db_session.refresh(uploaded_file)

    response = client.get(f"/api/files/{uploaded_file.id}/measurements/")

    assert response.status_code == 422
    assert response.json() == {"detail": "Unable to parse the uploaded file."}


def test_measurements_endpoint_returns_polygon_area(
    client: TestClient,
) -> None:
    """GET measurements returns calculated polygon area."""
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

    created = upload(
        client,
        "boundary.kml",
        content,
    )

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


def test_measurements_endpoint_handles_point(
    client: TestClient,
) -> None:
    """Point features do not receive an area or length measurement."""
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

    created = upload(
        client,
        "point.kml",
        content,
    )

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


def test_unknown_file_measurements_returns_not_found(
    client: TestClient,
) -> None:
    """Measurements endpoint returns 404 for an unknown file."""
    response = client.get(f"/api/files/{uuid4()}/measurements/")

    assert response.status_code == 404


def test_upload_real_shapefile_creates_ready_record(
    client: TestClient,
    tmp_path: Path,
) -> None:
    """A real Shapefile ZIP is parsed, measured, and persisted successfully."""
    content = real_shapefile_zip(tmp_path)

    response = upload(
        client,
        "boundary.zip",
        content,
    )

    assert response.status_code == 201

    payload = response.json()

    assert payload["status"] == "ready"
    assert payload["file_type"] == "shapefile_zip"
    assert payload["feature_count"] == 1
    assert payload["source_crs"] is not None

    file_id = payload["id"]

    measurements_response = client.get(f"/api/files/{file_id}/measurements/")

    assert measurements_response.status_code == 200

    measurement = measurements_response.json()["measurements"][0]

    assert measurement["geometry_type"] == "Polygon"
    assert measurement["measurement_type"] == "area"
    assert measurement["value"] is not None
    assert measurement["value"] > 0
    assert measurement["unit"] == "square_meters"
    assert measurement["calculation_crs"].startswith("EPSG:")
