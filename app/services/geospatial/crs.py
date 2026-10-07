"""Coordinate reference system utilities."""

from __future__ import annotations

import math

from pyproj import CRS, Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform


class CRSProcessingError(Exception):
    """Raised when CRS processing fails."""


class CRSService:
    """Handle CRS validation and geometry transformation."""

    def get_crs(self, crs_value: str | None) -> CRS:
        """Convert a CRS value into a PyProj CRS."""
        if not crs_value:
            raise CRSProcessingError("Source CRS is missing.")

        try:
            return CRS.from_user_input(crs_value)
        except Exception as error:
            raise CRSProcessingError(f"Invalid source CRS: {crs_value}") from error

    def get_calculation_crs(
        self,
        geometry: BaseGeometry,
        source_crs: str | None,
    ) -> CRS:
        """
        Return a projected CRS suitable for measurement.

        Geographic CRS are transformed into a local UTM zone.
        Already-projected CRS are retained.
        """
        crs = self.get_crs(source_crs)

        if not crs.is_geographic:
            return crs

        centroid = geometry.centroid

        longitude = centroid.x
        latitude = centroid.y

        if not (-180 <= longitude <= 180):
            raise CRSProcessingError("Invalid longitude.")

        if not (-90 <= latitude <= 90):
            raise CRSProcessingError("Invalid latitude.")

        zone = math.floor((longitude + 180) / 6) + 1

        if latitude >= 0:
            epsg = 32600 + zone
        else:
            epsg = 32700 + zone

        return CRS.from_epsg(epsg)

    def transform_for_measurement(
        self,
        geometry: BaseGeometry,
        source_crs: str | None,
        calculation_crs: CRS,
    ) -> BaseGeometry:
        """Transform geometry into the calculation CRS."""
        source = self.get_crs(source_crs)

        if source == calculation_crs:
            return geometry

        try:
            transformer = Transformer.from_crs(
                source,
                calculation_crs,
                always_xy=True,
            )

            return transform(transformer.transform, geometry)

        except Exception as error:
            raise CRSProcessingError("Unable to transform geometry.") from error
