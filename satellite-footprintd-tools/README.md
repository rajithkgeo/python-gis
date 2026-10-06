# Satellite Footprint Tools

Python tools for extracting satellite-image corner coordinates from metadata and converting those coordinates into GIS footprints.

The original workflow was developed around Cartosat metadata. This public version separates satellite-specific metadata names from the processing logic so the workflow can be adapted to other products.

## Workflow

```text
Satellite product ZIPs / folders
              |
              v
 extract_satellite_metadata.py
              |
              v
        Excel coordinates
              |
              v
       create_footprints.py
              |
              v
      GIS footprints (vector)
```

## Tools

### `extract_satellite_metadata.py`

Recursively searches a directory for ZIP archives and unpacked product folders. It looks for configured text metadata files and extracts the four image corners into a standardized Excel table.

### `create_footprints.py`

Reads the standardized Excel table and creates one polygon footprint per image. Output formats supported are GeoPackage, GeoJSON and Shapefile.

## Requirements

This is a **standalone Python workflow**.

Recommended: Python 3.10+

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

| Library | Purpose |
|---|---|
| pandas | Excel/tabular processing |
| openpyxl | Excel `.xlsx` support |
| geopandas | Geospatial data and GIS output |
| shapely | Polygon geometry |
| pyogrio | GIS file I/O backend |

## Installation on Windows

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Step 1 — Extract coordinates from metadata

Example:

```bash
python 1. extract_satellite_metadata.py 
```
Specify your input, output and the config file path when popped up.
The input folder can contain ZIP products or unpacked product folders.

The extractor does **not** need to unpack ZIP files before reading the metadata.

### Standardized Excel fields

```text
Source_Item
Metadata_File
UL_Lat
UL_Lon
UR_Lat
UR_Lon
LR_Lat
LR_Lon
LL_Lat
LL_Lon
Extraction_Status
```

## Step 2 — Create footprints

Recommended output:

```bash
python 2. create_footprints.py 
```
Specify your input excel file and output file (with format .gpkg/.geojson/.shp) path when popped up.

The footprint layer is written in **WGS 84 / EPSG:4326** because the input coordinate schema is geographic latitude/longitude.

## Coordinate order

The polygon is constructed in this order:

```text
UL ---------------- UR
 |                    |
 |                    |
LL ---------------- LR
```

The code passes coordinates to Shapely as `(longitude, latitude)`.

## Adapting to another satellite

Satellite products use different metadata file names and different field names. Edit:

```text
config/example_metadata_aliases.json
```

For example:

```json
"UL_Lat": [
    "ImageULLat",
    "UpperLeftLat",
    "MY_SATELLITE_UL_LAT"
]
```

Add the metadata key used by the new product to the appropriate list.

### Current scope

The extractor currently targets **text metadata containing simple `KEY = VALUE` or `KEY: VALUE` records**.

It is therefore not a universal parser for every satellite format. XML, JSON, GML, binary metadata and other specialized structures need an additional parser/adapter.

This design keeps the main footprint-generation workflow independent of a particular satellite.

## Validation and error handling

The extractor records an `Extraction_Status` column and reports missing corner fields.

The footprint generator:

- converts coordinate fields to numeric values
- removes incomplete rows
- validates latitude and longitude ranges
- reports how many records were skipped

## Why GeoPackage is recommended

GeoPackage is the preferred output for this project because it is a single portable GIS file and avoids many of the field-name and sidecar-file limitations of Shapefile.

## Author

**Rajith K**  
Geospatial | GIS | Remote Sensing | River Systems
