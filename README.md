# Geospatial File Measurement API

A production-oriented FastAPI service for uploading geospatial files, extracting their features and metadata, handling coordinate reference systems (CRS), and calculating geometry measurements such as polygon area and line length.

This project was developed as part of the **Aereo Software Development Engineer Internship Assignment**.

---

## 1. Overview

The API accepts geospatial files in the following formats:

- `.kml`
- `.zip` containing an ESRI Shapefile

For every uploaded file, the service:

1. Validates the uploaded file.
2. Stores the original file securely.
3. Parses the geospatial data.
4. Extracts feature metadata.
5. Identifies the source CRS.
6. Transforms geographic coordinates to an appropriate projected CRS when required.
7. Calculates measurements:
   - Polygon → area
   - LineString → length
   - Point → no measurement
8. Stores the processed feature data and measurements in PostgreSQL/PostGIS.
9. Exposes the results through REST APIs.

---

## 2. Features

### File Handling

- KML upload support
- ZIP-based Shapefile upload support
- File type validation
- File size validation
- SHA-256 file hashing
- Secure local file storage
- ZIP path traversal protection
- ZIP decompressed-size protection
- Validation of required Shapefile components

### Geospatial Processing

- Feature extraction
- Geometry type detection
- Feature properties extraction
- Source CRS extraction
- Polygon area calculation
- LineString length calculation
- Point handling without measurement
- MultiPolygon support
- MultiLineString support
- Unsupported geometry handling

### CRS Handling

- Geographic CRS detection
- Projected CRS support
- Automatic transformation from geographic CRS
- Local UTM CRS selection based on geometry location
- Accurate area and distance calculations in meters

### Backend

- FastAPI
- SQLAlchemy
- PostgreSQL
- PostGIS
- GeoAlchemy2
- Alembic migrations
- Pydantic schemas

### Quality

- Pytest automated tests
- Ruff linting
- Ruff formatting
- Docker Compose
- PostgreSQL/PostGIS health checks

---

## 3. Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11 |
| API | FastAPI |
| Database | PostgreSQL |
| Spatial Database | PostGIS |
| ORM | SQLAlchemy |
| Spatial ORM | GeoAlchemy2 |
| Migrations | Alembic |
| Geospatial Parsing | Fiona / ElementTree |
| Geometry Processing | Shapely |
| CRS Transformation | PyProj |
| Validation | Pydantic |
| Testing | Pytest |
| Linting | Ruff |
| Containerization | Docker / Docker Compose |

---

## 4. Architecture

```text
                     Client
                       |
                       | HTTP
                       v
              +-------------------+
              |     FastAPI       |
              |       API         |
              +-------------------+
                       |
                       v
              +-------------------+
              | File Validation   |
              | & Storage Service |
              +-------------------+
                       |
                       v
              +-------------------+
              | Geospatial Parser |
              | KML / Shapefile   |
              +-------------------+
                       |
                       v
              +-------------------+
              |  CRS Processing   |
              |   PyProj +        |
              |    Shapely        |
              +-------------------+
                       |
                       v
              +-------------------+
              | Measurement       |
              | Service           |
              +-------------------+
                       |
                       v
              +-------------------+
              | PostgreSQL +      |
              |    PostGIS        |
              +-------------------+

