"""Upload validation, geospatial processing, and persistence orchestration."""

from __future__ import annotations

import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from geoalchemy2.shape import from_shape
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import UploadValidationError
from app.db.models import GeospatialFeature, UploadedFile
from app.services.geospatial.measurement import MeasurementService
from app.services.geospatial.parser import (
    GeospatialParser,
    GeospatialParserError,
)
from app.storage.base import StorageBackend


class UploadIngestionService:
    """Validate, store, process, and persist geospatial uploads."""

    def __init__(self, settings: Settings, storage: StorageBackend) -> None:
        self.settings = settings
        self.storage = storage
        self.parser = GeospatialParser()
        self.measurement_service = MeasurementService()

    def ingest(
        self,
        *,
        stream,
        filename: str | None,
        content_type: str | None,
        session: Session,
    ) -> UploadedFile:
        """Persist and process a validated geospatial upload."""
        extension = self._validate_filename(filename)

        stored = self.storage.save(
            stream,
            extension,
            self.settings.max_upload_size_bytes,
        )

        uploaded_file = UploadedFile(
            original_filename=filename,
            file_type="kml" if extension == ".kml" else "shapefile_zip",
            content_type=content_type,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            storage_key=stored.key,
            status="processing",
        )

        session.add(uploaded_file)
        session.flush()

        try:
            if extension == ".zip":
                self._validate_shapefile_archive(Path(stored.path))

            with Path(stored.path).open("rb") as source:
                parsed_dataset = self.parser.parse(
                    stream=source,
                    filename=filename or "",
                    file_type=uploaded_file.file_type,
                )

            uploaded_file.source_crs = parsed_dataset.source_crs
            uploaded_file.feature_count = len(parsed_dataset.features)

            for parsed_feature in parsed_dataset.features:
                measurement = self.measurement_service.measure(
                    parsed_feature.geometry,
                    parsed_feature.source_crs,
                )

                database_feature = GeospatialFeature(
                    file_id=uploaded_file.id,
                    feature_index=parsed_feature.feature_index,
                    source_feature_id=parsed_feature.source_feature_id,
                    geometry_type=parsed_feature.geometry_type,
                    geometry=from_shape(
                        parsed_feature.geometry,
                        srid=-1,
                    ),
                    source_crs=parsed_feature.source_crs,
                    properties=parsed_feature.properties,
                    measurement_type=measurement.measurement_type,
                    measurement_value=measurement.value,
                    measurement_unit=measurement.unit,
                    measurement_crs=measurement.calculation_crs,
                )

                session.add(database_feature)

            uploaded_file.status = "ready"
            uploaded_file.processed_at = datetime.now(UTC)
            uploaded_file.error_code = None
            uploaded_file.error_message = None

            session.commit()
            session.refresh(uploaded_file)

            return uploaded_file

        except UploadValidationError:
            session.rollback()
            self.storage.delete(stored.key)
            raise

        except GeospatialParserError as error:
            session.rollback()

            uploaded_file.status = "failed"
            uploaded_file.error_code = type(error).__name__
            uploaded_file.error_message = str(error)

            session.add(uploaded_file)
            session.commit()
            session.refresh(uploaded_file)

            return uploaded_file

        except Exception as error:
            session.rollback()

            uploaded_file.status = "failed"
            uploaded_file.error_code = "PROCESSING_ERROR"
            uploaded_file.error_message = str(error)

            session.add(uploaded_file)
            session.commit()
            session.refresh(uploaded_file)

            return uploaded_file

    def _validate_filename(self, filename: str | None) -> str:
        if not filename or not filename.strip():
            raise UploadValidationError("An uploaded filename is required.")

        extension = Path(filename).suffix.lower()

        allowed_extensions = {value.lower() for value in self.settings.allowed_upload_extensions}

        if extension not in allowed_extensions:
            raise UploadValidationError(
                "Only .kml files and .zip Shapefile archives are supported."
            )

        return extension

    def _validate_shapefile_archive(self, archive_path: Path) -> None:
        try:
            with zipfile.ZipFile(archive_path) as archive:
                members = archive.infolist()

                if not members:
                    raise UploadValidationError("ZIP archive must not be empty.")

                total_uncompressed_size = 0
                file_names: list[str] = []

                for member in members:
                    self._validate_archive_member(member)

                    if member.is_dir():
                        continue

                    total_uncompressed_size += member.file_size

                    if total_uncompressed_size > self.settings.max_zip_uncompressed_size_bytes:
                        raise UploadValidationError(
                            "ZIP archive exceeds the configured decompressed size limit."
                        )

                    file_names.append(member.filename)

        except zipfile.BadZipFile as error:
            raise UploadValidationError("Uploaded ZIP archive is invalid.") from error

        shapefile_bases = {
            str(PurePosixPath(name).with_suffix(""))
            for name in file_names
            if PurePosixPath(name).suffix.lower() == ".shp"
        }

        if len(shapefile_bases) != 1:
            raise UploadValidationError("ZIP archive must contain exactly one Shapefile dataset.")

        base = next(iter(shapefile_bases))

        lower_file_names = {name.lower() for name in file_names}

        required_components = {
            f"{base}{extension}".lower() for extension in (".shp", ".shx", ".dbf")
        }

        if not required_components.issubset(lower_file_names):
            raise UploadValidationError(
                "ZIP archive must include .shp, .shx, and .dbf files for one dataset."
            )

    @staticmethod
    def _validate_archive_member(member: zipfile.ZipInfo) -> None:
        name = member.filename
        path = PurePosixPath(name)

        if (
            not name
            or "\x00" in name
            or "\\" in name
            or path.is_absolute()
            or ".." in path.parts
            or (path.parts and ":" in path.parts[0])
        ):
            raise UploadValidationError("ZIP archive contains an unsafe path.")

        if member.flag_bits & 0x1:
            raise UploadValidationError("Encrypted ZIP archives are not supported.")
