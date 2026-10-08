# Geospatial File Measurement API

A FastAPI service that accepts geospatial files, extracts their features and metadata, handles Coordinate Reference Systems (CRS), and computes geometry measurements: polygon **area** and line **length**, in metric units.

Built for the **Aereo Software Development Engineer Internship Assignment**.

---

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Tech Stack](#tech-stack)
4. [Architecture](#architecture)
5. [Quick Start](#quick-start)
6. [Verify the Setup](#verify-the-setup)
7. [API Reference](#api-reference)
8. [Supported Geometries](#supported-geometries)
9. [CRS Handling](#crs-handling)
10. [File Validation and Security](#file-validation-and-security)
11. [Error Handling](#error-handling)
12. [Database Design](#database-design)
13. [Testing and Code Quality](#testing-and-code-quality)
14. [Evaluation Walkthrough](#evaluation-walkthrough)
15. [Code Walkthrough](#code-walkthrough)
16. [Project Structure](#project-structure)
17. [Design Decisions](#design-decisions)
18. [Limitations](#limitations)
19. [Production Roadmap](#production-roadmap)
20. [Assignment Requirements Coverage](#assignment-requirements-coverage)

---

## Overview

The API accepts two file formats:

- `.kml`
- `.zip` containing an ESRI Shapefile

For every upload, the service:

1. Validates the file (type, size, archive safety).
2. Stores the original file and records its SHA-256 hash.
3. Parses the geospatial data.
4. Extracts feature metadata and properties.
5. Identifies the source CRS.
6. Transforms geographic coordinates to a suitable projected CRS when required.
7. Calculates measurements.
8. Persists features and measurements to PostgreSQL/PostGIS.
9. Exposes results through a REST API.

---

## Features

**File handling**
- KML and ZIP-based Shapefile upload
- File type and size validation
- SHA-256 hashing
- Secure local file storage
- ZIP path traversal and decompressed-size protection
- Required Shapefile component validation

**Geospatial processing**
- Feature, geometry type, and property extraction
- Source CRS extraction
- Area for Polygon and MultiPolygon
- Length for LineString and MultiLineString
- Point and MultiPoint handled without measurement
- Graceful handling of unsupported geometries

**CRS handling**
- Geographic and projected CRS detection
- Automatic transformation from geographic CRS
- Local UTM zone selection based on geometry location
- Accurate results in meters and square meters

**Backend and quality**
- FastAPI, SQLAlchemy, GeoAlchemy2, Alembic, Pydantic
- Pytest suite, Ruff linting and formatting
- Docker Compose with PostGIS health checks

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11 |
| API | FastAPI |
| Database | PostgreSQL + PostGIS |
| ORM | SQLAlchemy, GeoAlchemy2 |
| Migrations | Alembic |
| Parsing | Fiona, ElementTree |
| Geometry | Shapely |
| CRS transformation | PyProj |
| Validation | Pydantic |
| Testing | Pytest |
| Linting / formatting | Ruff |
| Containerization | Docker, Docker Compose |

---

## Architecture

```text
Client
  │  HTTP
  ▼
FastAPI API
  │
  ▼
File Validation & Storage Service
  │
  ▼
Geospatial Parser (KML / Shapefile)
  │
  ▼
CRS Processing (PyProj + Shapely)
  │
  ▼
Measurement Service
  │
  ▼
PostgreSQL + PostGIS
```

**Processing flow**

```text
Upload → Validate → Store + SHA-256 → Parse → Extract features/geometry/CRS
       → CRS processing → Transform geometry → Area/Length → Persist → Respond
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker Desktop
- Git

```bash
python --version
docker --version
git --version
```

### 1. Clone the repository

```bash
git clone <repository-url>
cd aereo-geospatial-measurement-api
```

Replace `<repository-url>` with the GitHub repository URL.

### 2. Create a virtual environment

**Windows (PowerShell)**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -e ".[dev]"
```

### 4. Configure environment variables

Copy the example file and adjust values if your environment needs it.

```bash
# Linux / macOS
cp .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

### 5. Start PostgreSQL + PostGIS

```bash
docker compose up -d
docker ps
```

The PostGIS container should show as running and healthy.

### 6. Run database migrations

```bash
alembic upgrade head
```

### 7. Start the API

```bash
uvicorn app.main:app --reload
```

The app is available at <http://127.0.0.1:8000>.

---

## Verify the Setup

**Health check:** <http://127.0.0.1:8000/health>

```json
{
  "status": "ok",
  "environment": "development",
  "version": "0.1.0"
}
```

**Swagger UI:** <http://127.0.0.1:8000/docs>

Swagger lets you upload KML and Shapefile ZIP files, fetch metadata and measurements, and inspect request/response schemas. No frontend is needed to evaluate the API.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Application health check |
| `POST` | `/api/files/` | Upload and process a geospatial file |
| `GET` | `/api/files/{id}` | Retrieve uploaded file metadata |
| `GET` | `/api/files/{id}/measurements/` | Retrieve calculated measurements |

### Upload a file

`POST /api/files/`

Successful response:

```json
{
  "id": "<file-id>",
  "original_filename": "test_shapefile.zip",
  "file_type": "shapefile_zip",
  "content_type": "application/x-zip-compressed",
  "size_bytes": 1090,
  "sha256": "<sha256>",
  "status": "ready",
  "source_crs": "<source-crs>",
  "feature_count": 1,
  "error_code": null,
  "error_message": null
}
```

Copy the returned `id` for the next calls.

### Get file metadata

`GET /api/files/{id}`

Returns the original filename, file type, content type, size, SHA-256, processing status, source CRS, feature count, any processing error, and creation and processing timestamps.

### Get measurements

`GET /api/files/{id}/measurements/`

```json
{
  "file_id": "<file-id>",
  "status": "ready",
  "measurements": [
    {
      "feature_index": 0,
      "geometry_type": "Polygon",
      "measurement_type": "area",
      "value": 12016.978112,
      "unit": "square_meters",
      "calculation_crs": "EPSG:32643"
    }
  ]
}
```

The exact value depends on the uploaded geometry.

---

## Supported Geometries

| Geometry | Measurement |
|---|---|
| Polygon | Area in square meters |
| MultiPolygon | Area in square meters |
| LineString | Length in meters |
| MultiLineString | Length in meters |
| Point | None |
| MultiPoint | None |
| Unsupported | Handled gracefully |

Point features return `not_applicable`:

```json
{
  "feature_index": 0,
  "geometry_type": "Point",
  "measurement_type": "not_applicable",
  "value": null,
  "unit": null,
  "calculation_crs": null
}
```

---

## CRS Handling

Geographic systems like EPSG:4326 use degrees, so area and distance are never computed directly on them. Instead the service:

1. Detects the source CRS.
2. Determines whether it is geographic or projected.
3. Selects a local projected CRS (UTM zone) when needed.
4. Transforms the geometry with PyProj and Shapely.
5. Measures the transformed geometry.

```text
EPSG:4326 (WGS84) → geographic CRS detected
   → select local UTM CRS (e.g. EPSG:32643)
   → transform geometry
   → calculate area / length in meters
```

---

## File Validation and Security

**General**
- Only `.kml` and `.zip` extensions are accepted.
- Upload size is limited.
- SHA-256 is computed for every file.
- Invalid archives are rejected.

**ZIP archives** are inspected before extraction. The service guards against:
- Path traversal
- Unsafe archive members
- Missing required Shapefile components
- Excessive decompressed size

This prevents archives from writing outside the storage location or exhausting resources.

---

## Error Handling

| Scenario | Result |
|---|---|
| Unsupported file extension | `422` |
| Invalid ZIP archive | Validation error |
| Missing Shapefile components | Validation error |
| Unsafe ZIP path | Validation error |
| Excessive decompressed size | Validation error |
| Unknown file ID | `404` |
| File still processing | `409` |
| Processing failure | `422` |

For failed processing, the error code and message are stored on the uploaded file and can be retrieved through the API.

---

## Database Design

PostgreSQL with PostGIS.

**`uploaded_files`**
UUID, original filename, file type, content type, size, SHA-256, storage key, status, source CRS, feature count, error code, error message, created and processed timestamps.

**`geospatial_features`**
Feature UUID, uploaded file ID, feature index, source feature ID, geometry type, geometry, source CRS, properties, measurement type, value, unit, CRS, and metadata.

A GiST spatial index is used on the geometry column.

---

## Testing and Code Quality

```bash
# Tests
python -m pytest -q

# Lint
python -m ruff check .

# Format check
python -m ruff format --check .

# Whitespace check
git diff --check
```

All checks should pass before submission.

The test suite covers: upload, file type and size validation, SHA-256 hashing, KML and Shapefile parsing, ZIP validation (path traversal, decompressed size, required components), metadata persistence, CRS detection and transformation, all geometry measurements, unsupported geometries, API integration, processing and failure states, and unknown file IDs.

---

## Evaluation Walkthrough

1. Clone the repository
2. Create a virtual environment
3. Install dependencies
4. Start PostgreSQL/PostGIS
5. Run Alembic migrations
6. Start FastAPI
7. Open Swagger at `/docs`
8. Upload a KML Polygon, then fetch measurements
9. Upload a KML LineString, then fetch measurements
10. Upload a KML Point and verify no measurement
11. Upload a Shapefile ZIP, then fetch the polygon area
12. Run the automated tests
13. Run the Ruff checks

### Expected results

| Input | Expected |
|---|---|
| KML Polygon | `geometry_type: Polygon`, `measurement_type: area`, `unit: square_meters` |
| KML LineString | `geometry_type: LineString`, `measurement_type: length`, `unit: meters` |
| KML Point | `geometry_type: Point`, `measurement_type: not_applicable`, `value: null` |
| Shapefile ZIP | `file_type: shapefile_zip`, `status: ready`, `feature_count >= 1` |
| `test.txt` | `422 Unprocessable Entity` |
| Corrupted ZIP | Rejected gracefully |
| Unknown UUID | `404 Not Found` |

A valid Shapefile ZIP contains the required components:

```text
example.zip
├── example.shp
├── example.shx
├── example.dbf
└── example.prj
```

---

## Code Walkthrough

| Area | Location |
|---|---|
| API routes | `app/api/routes/files.py` |
| Upload and file handling | `app/services/file_service.py` |
| Geospatial parser | `app/services/geospatial/parser.py` |
| CRS processing | `app/services/geospatial/crs.py` |
| Measurement calculation | `app/services/geospatial/measurement.py` |
| Ingestion pipeline | `app/services/ingestion.py` |
| Database models | `app/db/models.py` |
| API schemas | `app/schemas/file.py` |
| Migrations | `alembic/` |
| API integration tests | `tests/db/test_files_api.py` |
| Geospatial tests | `tests/services/geospatial/` |

**Suggested review path:** API route → file service → ingestion service → parser → CRS service → measurement service → PostgreSQL/PostGIS.

---

## Project Structure

```text
aereo-geospatial-measurement-api/
├── app/
│   ├── api/
│   │   └── routes/
│   ├── db/
│   ├── schemas/
│   ├── services/
│   │   └── geospatial/
│   └── main.py
├── alembic/
│   └── versions/
├── tests/
│   ├── db/
│   └── services/
│       └── geospatial/
├── storage/
├── docker-compose.yml
├── alembic.ini
├── pyproject.toml
├── README.md
└── .env.example
```

---

## Design Decisions

**Synchronous processing.** Files are processed within the request, so clients get results immediately and the architecture stays simple. For larger files or higher traffic, move processing to a queue-backed worker.

**Storage abstraction.** Uploads go through a storage interface, so the local filesystem can be swapped for object storage such as S3 without touching the API layer.

**PostgreSQL + PostGIS.** Chosen for native geometry storage and spatial indexing.

**Generic geometry column.** Source geometry is preserved in its own CRS rather than forced into one, and measurement geometry is transformed independently.

**CRS-aware measurements.** Geographic geometries are always projected before measuring, never measured in degrees.

---

## Limitations

The implementation focuses on the assignment requirements. Known limitations:

- Synchronous file processing
- Local filesystem storage only
- No authentication or authorization
- No background processing queue
- CRS strategy is primarily local UTM selection
- No frontend
- No production monitoring or observability stack

---

## Production Roadmap

- S3-compatible object storage
- Background processing (Celery or RQ) with Redis-backed job status
- Authentication, authorization, and rate limiting
- Structured logging, metrics, and distributed tracing
- Large-file streaming
- More advanced CRS selection
- Spatial query endpoints
- Frontend map visualization
- Cloud deployment and horizontal API scaling

**Target async architecture**

```text
Client → FastAPI → Object Storage → Job Queue → Background Worker
                                                   ├─ Geospatial Parser
                                                   ├─ CRS Processing
                                                   └─ Measurement
                                                        ↓
                                              PostgreSQL + PostGIS → API
```

---

## Assignment Requirements Coverage

| Requirement | Implementation |
|---|---|
| FastAPI / Django | FastAPI |
| `.kml` upload | Implemented |
| Shapefile `.zip` upload | Implemented |
| Feature extraction (ID/index, geometry type, geometry, properties) | Implemented |
| CRS extraction | Implemented |
| Polygon / MultiPolygon area | Implemented |
| LineString / MultiLineString length | Implemented |
| Point handling | Implemented |
| Unsupported geometry | Implemented |
| Geographic and projected CRS handling | Implemented |
| CRS transformation | Implemented |
| `POST /api/files/` | Implemented |
| `GET /api/files/{id}` | Implemented |
| `GET /api/files/{id}/measurements/` | Implemented |
| Automated tests | Implemented |
| PostgreSQL/PostGIS | Implemented |
| Docker | Implemented |
| Database migrations | Alembic |
| API documentation | FastAPI / Swagger |

---

## Assignment

Developed as part of the Aereo Software Development Engineer Internship Assignment.