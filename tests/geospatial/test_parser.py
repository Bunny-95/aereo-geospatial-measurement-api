"""Tests for geospatial parsing."""

import io
import zipfile

import pytest
from app.services.geospatial.parser import (
    GeospatialParser,
    GeospatialParserError,
)


def test_parser_rejects_unsupported_type():
    parser = GeospatialParser()

    with pytest.raises(GeospatialParserError, match="Unsupported file type"):
        parser.parse(
            stream=io.BytesIO(b"test"),
            filename="test.txt",
            file_type="txt",
        )


def test_parser_rejects_invalid_shapefile_zip():
    parser = GeospatialParser()

    with pytest.raises(GeospatialParserError):
        parser.parse(
            stream=io.BytesIO(b"not-a-zip"),
            filename="test.zip",
            file_type="shapefile_zip",
        )


def test_parser_rejects_empty_zip():
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w"):
        pass

    buffer.seek(0)

    parser = GeospatialParser()

    with pytest.raises(GeospatialParserError, match="empty"):
        parser.parse(
            stream=buffer,
            filename="empty.zip",
            file_type="shapefile_zip",
        )
