# Aereo Geospatial Measurement API

Backend service for ingesting geospatial files and reporting feature measurements. This repository currently provides the application and PostGIS persistence foundations; file ingestion and measurements will be added in later phases.

## Requirements

- Python 3.11
- Docker Desktop with Docker Compose

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

## PostgreSQL + PostGIS

Start the local database service:

```powershell
docker compose up -d db
docker compose ps
```

The development defaults are deliberately local-only and are configured in `.env.example`. The host maps port `5433` to PostgreSQL's container port `5432`, avoiding collision with an existing local PostgreSQL installation. Docker Compose stores database data in the named `postgis_data` volume. No application container is included yet.

Run the initial migration after the database becomes healthy:

```powershell
alembic upgrade head
alembic current
```

To stop the service while retaining data:

```powershell
docker compose down
```

## Run locally

```powershell
uvicorn app.main:app --reload
```

The health endpoint is available at `GET /health`.

## Upload API

`POST /api/files/` accepts one multipart field named `file`. Supported inputs are `.kml` files and `.zip` archives containing exactly one Shapefile dataset with `.shp`, `.shx`, and `.dbf` components. Geospatial parsing is not performed yet; accepted uploads remain in `processing` status.

```powershell
curl.exe -X POST http://localhost:8000/api/files/ -F "file=@.\boundary.kml"
```

Example response:

```json
{
  "id": "33f30bc1-1ddc-48e7-b3a6-2cf14a432c4b",
  "original_filename": "boundary.kml",
  "file_type": "kml",
  "content_type": "application/vnd.google-earth.kml+xml",
  "size_bytes": 184,
  "sha256": "...",
  "status": "processing",
  "source_crs": null,
  "feature_count": 0,
  "error_code": null,
  "error_message": null,
  "created_at": "2026-10-07T12:00:00Z",
  "processed_at": null
}
```

Retrieve public metadata with `GET /api/files/{id}`. Internal storage keys and filesystem paths are never returned.

### Upload limits and storage safety

- `MAX_UPLOAD_SIZE_BYTES` defaults to 10 MiB; files are streamed in chunks while SHA-256 is calculated.
- `MAX_ZIP_UNCOMPRESSED_SIZE_BYTES` defaults to 50 MiB.
- `UPLOAD_DIRECTORY` defaults to `data/uploads` and is created automatically.
- Stored object keys are UUID-based; user filenames are metadata only and are never used as filesystem paths.
- ZIP archives are inspected without extraction. Traversal paths, encrypted members, invalid archives, incomplete Shapefiles, multiple datasets, and oversized decompressed content are rejected.
- If validation or database persistence fails, the stored object is removed where possible.

## Database architecture

- `uploaded_files` stores source-file metadata, source CRS, processing state, and error details.
- `geospatial_features` stores source feature metadata, JSONB attributes, source geometry, and fields reserved for later measurements.
- Features reference their owning upload through `file_id`; `(file_id, feature_index)` is unique.
- The geometry column uses the PostGIS generic `geometry(GEOMETRY, -1)` form with a GIST index. It accepts any source geometry type and SRID instead of coercing all data to EPSG:4326. `source_crs` persists the original declared CRS, including non-EPSG CRS strings. Later processing will create projected copies only for calculations, leaving source geometry intact.

## Migrations

Alembic reads the same `DATABASE_*` settings as the application. Common commands:

```powershell
alembic upgrade head
alembic current
alembic downgrade -1
```

## Verification

```powershell
pytest
ruff check .
ruff format --check .
```

## Current scope

Phase 2 adds synchronous SQLAlchemy 2.x sessions, GeoAlchemy2/PostGIS models, Alembic migration support, Docker Compose database infrastructure, and PostgreSQL integration tests. No file upload, parsing, CRS transformation, or measurements are implemented yet.
