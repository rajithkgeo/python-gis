from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon

FIELDS = ["UL_Lat", "UL_Lon", "UR_Lat", "UR_Lon", "LR_Lat", "LR_Lon", "LL_Lat", "LL_Lon"]
ALIASES = {
    "UL_Lat": ["UL_Lat", "ImageULLat"], "UL_Lon": ["UL_Lon", "ImageULLon"],
    "UR_Lat": ["UR_Lat", "ImageURLat"], "UR_Lon": ["UR_Lon", "ImageURLon"],
    "LR_Lat": ["LR_Lat", "ImageLRLat"], "LR_Lon": ["LR_Lon", "ImageLRLon"],
    "LL_Lat": ["LL_Lat", "ImageLLLat"], "LL_Lon": ["LL_Lon", "ImageLLLon"],
}


def standardize(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for standard, names in ALIASES.items():
        found = next((n for n in names if n in df.columns), None)
        if found is None:
            raise ValueError(f"Missing coordinate field for {standard}. Accepted names: {names}")
        rename[found] = standard
    return df.rename(columns=rename)


def make_polygon(row: pd.Series) -> Polygon:
    return Polygon([
        (row["UL_Lon"], row["UL_Lat"]),
        (row["UR_Lon"], row["UR_Lat"]),
        (row["LR_Lon"], row["LR_Lat"]),
        (row["LL_Lon"], row["LL_Lat"]),
    ])


def get_interactive_paths() -> tuple[Path, Path, str]:
    """Prompts the user interactively in the console for input Excel and output GIS paths."""
    print("=" * 60)
    print(" SATELLITE FOOTPRINT GENERATION TOOL (Interactive Mode)")
    print("=" * 60)

    # 1. Input Excel path prompt
    default_input = r"D:\Satellite data\Satellite_Coordinates.xlsx"
    raw_input = input(f"Enter input Excel file path [Default: {default_input}]: ").strip().strip('"')
    input_path = Path(raw_input if raw_input else default_input)

    # 2. Output vector file path prompt (.gpkg, .geojson, .shp)
    default_output = r"D:\Satellite data\Image_Footprints.gpkg"
    raw_output = input(f"Enter output vector path (.gpkg / .geojson / .shp) [Default: {default_output}]: ").strip().strip('"')
    output_path = Path(raw_output if raw_output else default_output)

    # 3. Layer name prompt (relevant for GeoPackage .gpkg format)
    default_layer = "footprints"
    raw_layer = input(f"Enter layer name [Default: {default_layer}]: ").strip()
    layer_name = raw_layer if raw_layer else default_layer

    print("-" * 60)
    return input_path, output_path, layer_name


def main() -> None:
    # Get paths via interactive user input
    input_path, output_path, layer_name = get_interactive_paths()

    if not input_path.exists():
        raise SystemExit(f"Input Excel file does not exist: {input_path}")

    df = standardize(pd.read_excel(input_path))
    for field in FIELDS:
        df[field] = pd.to_numeric(df[field], errors="coerce")
    original = len(df)
    df = df.dropna(subset=FIELDS).copy()

    valid = (
        df[["UL_Lat", "UR_Lat", "LR_Lat", "LL_Lat"]].ge(-90).all(axis=1)
        & df[["UL_Lat", "UR_Lat", "LR_Lat", "LL_Lat"]].le(90).all(axis=1)
        & df[["UL_Lon", "UR_Lon", "LR_Lon", "LL_Lon"]].ge(-180).all(axis=1)
        & df[["UL_Lon", "UR_Lon", "LR_Lon", "LL_Lon"]].le(180).all(axis=1)
    )
    invalid = int((~valid).sum())
    df = df.loc[valid].copy()
    if df.empty:
        raise SystemExit("No valid coordinate records remain after validation.")

    df["geometry"] = df.apply(make_polygon, axis=1)
    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    suffix = output_path.suffix.lower()
    if suffix == ".gpkg":
        gdf.to_file(output_path, layer=layer_name, driver="GPKG")
    elif suffix in {".geojson", ".json"}:
        gdf.to_file(output_path, driver="GeoJSON")
    elif suffix == ".shp":
        gdf.to_file(output_path, driver="ESRI Shapefile")
    else:
        raise SystemExit("Use an output extension of .gpkg, .geojson or .shp")

    print("\nFootprint generation completed.")
    print(f"Input rows          : {original:,}")
    print(f"Footprints created  : {len(gdf):,}")
    print(f"Incomplete rows     : {original - len(df) - invalid:,}")
    print(f"Invalid coordinates : {invalid:,}")
    print(f"Output              : {output_path}")


if __name__ == "__main__":
    main()