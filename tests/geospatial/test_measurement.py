"""Tests for CRS transformation and geometry measurements."""

import pytest
from app.services.geospatial.measurement import MeasurementService
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPolygon,
    Point,
    Polygon,
)


def test_polygon_area_in_wgs84_is_measured_in_square_meters():
    geometry = Polygon(
        [
            (77.5946, 12.9716),
            (77.5956, 12.9716),
            (77.5956, 12.9726),
            (77.5946, 12.9726),
            (77.5946, 12.9716),
        ]
    )

    result = MeasurementService().measure(
        geometry,
        "EPSG:4326",
    )

    assert result.measurement_type == "area"
    assert result.unit == "square_meters"
    assert result.value is not None
    assert result.value > 0
    assert result.calculation_crs is not None
    assert result.calculation_crs.startswith("EPSG:")


def test_linestring_in_wgs84_is_measured_in_meters():
    geometry = LineString(
        [
            (77.5946, 12.9716),
            (77.6046, 12.9716),
        ]
    )

    result = MeasurementService().measure(
        geometry,
        "EPSG:4326",
    )

    assert result.measurement_type == "length"
    assert result.unit == "meters"
    assert result.value is not None
    assert result.value > 0


def test_point_has_no_measurement():
    """Point geometries should not produce an area or length."""
    service = MeasurementService()

    result = service.measure(
        geometry=Point(77.5946, 12.9716),
        source_crs="EPSG:4326",
    )

    assert result.measurement_type == "not_applicable"
    assert result.value is None
    assert result.unit is None
    assert result.calculation_crs is None


def test_projected_crs_is_used_directly():
    geometry = Polygon(
        [
            (500000, 1430000),
            (500100, 1430000),
            (500100, 1430100),
            (500000, 1430100),
            (500000, 1430000),
        ]
    )

    result = MeasurementService().measure(
        geometry,
        "EPSG:32643",
    )

    assert result.measurement_type == "area"
    assert result.value == pytest.approx(10000, rel=0.01)
    assert result.unit == "square_meters"
    assert result.calculation_crs == "EPSG:32643"


def test_missing_crs_raises_error():
    geometry = LineString(
        [
            (0, 0),
            (100, 100),
        ]
    )

    with pytest.raises(Exception, match="Source CRS is missing"):
        MeasurementService().measure(
            geometry,
            None,
        )


def test_multipolygon_returns_area():
    """MultiPolygon geometries should return area in square metres."""
    service = MeasurementService()

    geometry = MultiPolygon(
        [
            Polygon(
                [
                    (77.5940, 12.9710),
                    (77.5950, 12.9710),
                    (77.5950, 12.9720),
                    (77.5940, 12.9720),
                    (77.5940, 12.9710),
                ]
            )
        ]
    )

    result = service.measure(
        geometry=geometry,
        source_crs="EPSG:4326",
    )

    assert result.measurement_type == "area"
    assert result.value is not None
    assert result.value > 0
    assert result.unit == "square_meters"
    assert result.calculation_crs.startswith("EPSG:")


def test_multilinestring_returns_length():
    """MultiLineString geometries should return length in metres."""
    service = MeasurementService()

    geometry = MultiLineString(
        [
            [
                (77.5940, 12.9710),
                (77.5950, 12.9710),
            ]
        ]
    )

    result = service.measure(
        geometry=geometry,
        source_crs="EPSG:4326",
    )

    assert result.measurement_type == "length"
    assert result.value is not None
    assert result.value > 0
    assert result.unit == "meters"
    assert result.calculation_crs.startswith("EPSG:")


def test_unsupported_geometry_is_handled():
    """Unsupported geometry types should not crash measurement processing."""
    service = MeasurementService()

    geometry = GeometryCollection(
        [
            Point(77.5946, 12.9716),
        ]
    )

    result = service.measure(
        geometry=geometry,
        source_crs="EPSG:4326",
    )

    assert result.measurement_type == "unsupported"
    assert result.value is None
    assert result.unit is None
