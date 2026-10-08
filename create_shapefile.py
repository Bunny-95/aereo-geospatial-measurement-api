from pathlib import Path
from zipfile import ZipFile

import fiona


output_dir = Path("test_shapefile")
output_dir.mkdir(exist_ok=True)

shp_path = output_dir / "test_polygon.shp"

schema = {
    "geometry": "Polygon",
    "properties": {
        "name": "str:80",
    },
}

polygon = {
    "type": "Polygon",
    "coordinates": [
        [
            [77.5946, 12.9716],
            [77.5956, 12.9716],
            [77.5956, 12.9726],
            [77.5946, 12.9726],
            [77.5946, 12.9716],
        ]
    ],
}

# Create a real Shapefile
with fiona.open(
    shp_path,
    "w",
    driver="ESRI Shapefile",
    schema=schema,
    crs="EPSG:4326",
) as collection:
    collection.write(
        {
            "geometry": polygon,
            "properties": {
                "name": "Test Polygon",
            },
        }
    )

# Create ZIP containing all required Shapefile components
zip_path = Path("test_shapefile.zip")

with ZipFile(zip_path, "w") as zip_file:
    for extension in [".shp", ".shx", ".dbf", ".prj"]:
        file_path = output_dir / f"test_polygon{extension}"
        zip_file.write(
            file_path,
            arcname=file_path.name,
        )

print(f"Created: {zip_path}")
print("ZIP contents:")

with ZipFile(zip_path, "r") as zip_file:
    for name in zip_file.namelist():
        print(f"  - {name}")