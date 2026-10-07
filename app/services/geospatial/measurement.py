"""Geometry measurement utilities."""

from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import (
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)
from shapely.geometry.base import BaseGeometry

from app.services.geospatial.crs import CRSService


class MeasurementError(Exception):
    """Raised when geometry measurement fails."""


@dataclass
class MeasurementResult:
    """Result of measuring one geometry."""

    measurement_type: str
    value: float | None
    unit: str | None
    calculation_crs: str | None


class MeasurementService:
    """Calculate measurements for supported geometry types."""

    def __init__(self, crs_service: CRSService | None = None) -> None:
        self.crs_service = crs_service or CRSService()

    def measure(
        self,
        geometry: BaseGeometry,
        source_crs: str | None,
    ) -> MeasurementResult:
        """Calculate the appropriate measurement for a geometry."""

        if isinstance(geometry, (Point, MultiPoint)):
            return MeasurementResult(
                measurement_type="not_applicable",
                value=None,
                unit=None,
                calculation_crs=None,
            )

        if isinstance(
            geometry,
            (Polygon, MultiPolygon, LineString, MultiLineString),
        ):
            calculation_crs = self.crs_service.get_calculation_crs(
                geometry,
                source_crs,
            )

            projected_geometry = self.crs_service.transform_for_measurement(
                geometry,
                source_crs,
                calculation_crs,
            )

            if isinstance(projected_geometry, (Polygon, MultiPolygon)):
                value = projected_geometry.area
                measurement_type = "area"
                unit = "square_meters"

            else:
                value = projected_geometry.length
                measurement_type = "length"
                unit = "meters"

            return MeasurementResult(
                measurement_type=measurement_type,
                value=float(value),
                unit=unit,
                calculation_crs=calculation_crs.to_string(),
            )

        return MeasurementResult(
            measurement_type="unsupported",
            value=None,
            unit=None,
            calculation_crs=None,
        )
