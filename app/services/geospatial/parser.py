"""KML and Shapefile parsing."""

from __future__ import annotations

import json
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import BinaryIO

import fiona
from shapely.geometry import (
    LineString,
    Point,
    Polygon,
    shape,
)

from app.services.geospatial.models import ParsedDataset, ParsedFeature


class GeospatialParserError(Exception):
    """Raised when a geospatial file cannot be parsed."""


class GeospatialParser:
    """Parse supported geospatial file formats into normalized features."""

    REQUIRED_SHAPEFILE_COMPONENTS = {".shp", ".shx", ".dbf"}

    def parse(
        self,
        stream: BinaryIO,
        filename: str,
        file_type: str,
    ) -> ParsedDataset:
        """Parse a supported geospatial file."""
        if file_type == "kml":
            return self._parse_kml(stream)

        if file_type == "shapefile_zip":
            return self._parse_shapefile_zip(stream)

        raise GeospatialParserError(f"Unsupported file type: {file_type}")

    def _parse_kml(self, stream: BinaryIO) -> ParsedDataset:
        """Parse KML using XML and Shapely instead of Fiona."""
        try:
            content = stream.read()

            if not content:
                raise GeospatialParserError("KML file is empty.")

            root = ET.fromstring(content)

            namespace = self._get_kml_namespace(root)
            placemarks = root.findall(f".//{{{namespace}}}Placemark")

            features: list[ParsedFeature] = []

            for index, placemark in enumerate(placemarks):
                geometry = self._parse_kml_geometry(placemark, namespace)

                if geometry is None:
                    raise GeospatialParserError(
                        f"Placemark {index} does not contain a supported geometry."
                    )

                if geometry.is_empty:
                    raise GeospatialParserError(f"Placemark {index} contains empty geometry.")

                properties = self._parse_kml_properties(
                    placemark,
                    namespace,
                )

                source_feature_id = placemark.get("id")

                features.append(
                    ParsedFeature(
                        feature_index=index,
                        source_feature_id=source_feature_id,
                        geometry_type=geometry.geom_type,
                        geometry=geometry,
                        properties=properties,
                        source_crs="EPSG:4326",
                    )
                )

            return ParsedDataset(
                source_crs="EPSG:4326",
                features=features,
            )

        except GeospatialParserError:
            raise
        except ET.ParseError as error:
            raise GeospatialParserError(f"Invalid KML XML: {error}") from error
        except Exception as error:
            raise GeospatialParserError(f"Unable to parse KML file: {error}") from error

    @staticmethod
    def _get_kml_namespace(root: ET.Element) -> str:
        """Get the KML XML namespace."""
        if root.tag.startswith("{"):
            return root.tag[1 : root.tag.index("}")]

        raise GeospatialParserError("KML document does not contain a valid XML namespace.")

    @classmethod
    def _parse_kml_geometry(
        cls,
        placemark: ET.Element,
        namespace: str,
    ):
        """Extract the first supported geometry from a KML Placemark."""
        point = placemark.find(f".//{{{namespace}}}Point")
        if point is not None:
            coordinates = cls._parse_coordinates(
                point.find(f".//{{{namespace}}}coordinates"),
            )
            return Point(coordinates[0])

        linestring = placemark.find(f".//{{{namespace}}}LineString")
        if linestring is not None:
            coordinates = cls._parse_coordinates(
                linestring.find(f".//{{{namespace}}}coordinates"),
            )
            return LineString(coordinates)

        polygon = placemark.find(f".//{{{namespace}}}Polygon")
        if polygon is not None:
            return cls._parse_polygon(polygon, namespace)

        return None

    @classmethod
    def _parse_polygon(
        cls,
        polygon: ET.Element,
        namespace: str,
    ) -> Polygon:
        """Parse a KML Polygon including optional inner boundaries."""
        outer = polygon.find(
            f".//{{{namespace}}}outerBoundaryIs"
            f"/{{{namespace}}}LinearRing"
            f"/{{{namespace}}}coordinates"
        )

        if outer is None:
            raise GeospatialParserError("Polygon does not contain an outer boundary.")

        outer_coordinates = cls._parse_coordinates(outer)

        holes: list[list[tuple[float, float]]] = []

        for inner in polygon.findall(
            f".//{{{namespace}}}innerBoundaryIs"
            f"/{{{namespace}}}LinearRing"
            f"/{{{namespace}}}coordinates"
        ):
            holes.append(cls._parse_coordinates(inner))

        return Polygon(outer_coordinates, holes)

    @staticmethod
    def _parse_coordinates(
        element: ET.Element | None,
    ) -> list[tuple[float, float]]:
        """Parse KML coordinate text into longitude/latitude pairs."""
        if element is None or not element.text:
            raise GeospatialParserError("KML geometry does not contain coordinates.")

        coordinates: list[tuple[float, float]] = []

        for value in element.text.split():
            parts = value.split(",")

            if len(parts) < 2:
                raise GeospatialParserError(f"Invalid KML coordinate: {value}")

            try:
                longitude = float(parts[0])
                latitude = float(parts[1])
            except ValueError as error:
                raise GeospatialParserError(f"Invalid KML coordinate: {value}") from error

            coordinates.append((longitude, latitude))

        if not coordinates:
            raise GeospatialParserError("KML geometry contains no coordinates.")

        return coordinates

    @staticmethod
    def _parse_kml_properties(
        placemark: ET.Element,
        namespace: str,
    ) -> dict[str, object]:
        """Extract simple KML properties from a Placemark."""
        properties: dict[str, object] = {}

        name = placemark.find(f"{{{namespace}}}name")

        if name is not None and name.text:
            properties["name"] = name.text

        description = placemark.find(f"{{{namespace}}}description")

        if description is not None and description.text:
            properties["description"] = description.text

        return properties

    def _parse_shapefile_zip(
        self,
        stream: BinaryIO,
    ) -> ParsedDataset:
        """Safely extract and parse a Shapefile ZIP archive."""
        with tempfile.TemporaryDirectory(prefix="aereo-shapefile-") as temp_dir:
            temp_path = Path(temp_dir)
            zip_path = temp_path / "input.zip"

            with zip_path.open("wb") as output:
                self._copy_stream(stream, output)

            try:
                with zipfile.ZipFile(zip_path) as archive:
                    self._validate_zip_members(
                        archive,
                        temp_path,
                    )
                    archive.extractall(temp_path)

            except zipfile.BadZipFile as error:
                raise GeospatialParserError("Invalid ZIP archive.") from error

            shapefile_path = self._find_shapefile(temp_path)

            if shapefile_path is None:
                raise GeospatialParserError("ZIP archive does not contain a complete Shapefile.")

            try:
                return self._read_dataset(shapefile_path)
            except Exception as error:
                raise GeospatialParserError(f"Unable to parse Shapefile: {error}") from error

    def _read_dataset(
        self,
        path: Path,
        default_crs: str | None = None,
    ) -> ParsedDataset:
        """Read a Fiona dataset and normalize its features."""
        try:
            with fiona.open(path) as source:
                source_crs = self._extract_crs(source)

                if source_crs is None:
                    source_crs = default_crs

                features: list[ParsedFeature] = []

                for index, feature in enumerate(source):
                    geometry_data = feature.get("geometry")

                    if geometry_data is None:
                        raise GeospatialParserError(f"Feature {index} does not contain geometry.")

                    geometry = shape(geometry_data)

                    if geometry.is_empty:
                        raise GeospatialParserError(f"Feature {index} contains empty geometry.")

                    properties = dict(feature.get("properties") or {})

                    source_feature_id = feature.get("id")

                    if source_feature_id is not None:
                        source_feature_id = str(source_feature_id)

                    features.append(
                        ParsedFeature(
                            feature_index=index,
                            source_feature_id=source_feature_id,
                            geometry_type=geometry.geom_type,
                            geometry=geometry,
                            properties=properties,
                            source_crs=source_crs,
                        )
                    )

                return ParsedDataset(
                    source_crs=source_crs,
                    features=features,
                )

        except GeospatialParserError:
            raise

    @staticmethod
    def _extract_crs(
        source: fiona.Collection,
    ) -> str | None:
        """Extract CRS information from a Fiona collection."""
        if source.crs_wkt:
            return source.crs_wkt

        if source.crs:
            return json.dumps(dict(source.crs))

        return None

    @staticmethod
    def _copy_stream(
        stream: BinaryIO,
        destination: BinaryIO,
    ) -> None:
        """Copy an input stream efficiently."""
        while True:
            chunk = stream.read(1024 * 1024)

            if not chunk:
                break

            destination.write(chunk)

    @classmethod
    def _validate_zip_members(
        cls,
        archive: zipfile.ZipFile,
        extraction_dir: Path,
    ) -> None:
        """Validate archive paths before extraction."""
        members = archive.infolist()

        if not members:
            raise GeospatialParserError("ZIP archive is empty.")

        for member in members:
            member_path = Path(member.filename)

            if member.filename.startswith("/"):
                raise GeospatialParserError("ZIP archive contains an absolute path.")

            if ".." in member_path.parts:
                raise GeospatialParserError("ZIP archive contains an unsafe path.")

            target = (extraction_dir / member.filename).resolve()

            if not target.is_relative_to(extraction_dir.resolve()):
                raise GeospatialParserError("ZIP archive contains a path traversal attempt.")

    @classmethod
    def _find_shapefile(
        cls,
        directory: Path,
    ) -> Path | None:
        """Find a complete Shapefile inside an extracted directory."""
        shapefiles = list(directory.rglob("*.shp"))

        for shp_path in shapefiles:
            stem = shp_path.with_suffix("")

            components = {
                suffix
                for suffix in cls.REQUIRED_SHAPEFILE_COMPONENTS
                if stem.with_suffix(suffix).exists()
            }

            if components == cls.REQUIRED_SHAPEFILE_COMPONENTS:
                return shp_path

        return None
