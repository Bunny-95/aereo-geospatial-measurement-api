"""Models used by the geospatial parsing layer."""

from dataclasses import dataclass
from typing import Any


@dataclass
class ParsedFeature:
    """Normalized representation of one source feature."""

    feature_index: int
    source_feature_id: str | None
    geometry_type: str
    geometry: Any
    properties: dict[str, Any]
    source_crs: str | None


@dataclass
class ParsedDataset:
    """Result of parsing an uploaded geospatial dataset."""

    source_crs: str | None
    features: list[ParsedFeature]
