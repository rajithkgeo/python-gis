from __future__ import annotations

import fnmatch
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Iterable

import pandas as pd

FIELDS = ["UL_Lat", "UL_Lon", "UR_Lat", "UR_Lon", "LR_Lat", "LR_Lon", "LL_Lat", "LL_Lon"]


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def load_config(path: Path) -> tuple[list[str], dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)
    patterns = cfg.get("metadata_file_patterns", [])
    mapping: dict[str, str] = {}
    for standard, aliases in cfg.get("corner_fields", {}).items():
        for alias in aliases:
            mapping[normalize_key(alias)] = standard
    missing = [f for f in FIELDS if f not in cfg.get("corner_fields", {})]
    if missing:
        raise ValueError(f"Config is missing fields: {missing}")
    if not patterns:
        raise ValueError("Config must contain metadata_file_patterns.")
    return patterns, mapping


def parse_line(line: str) -> tuple[str, str] | None:
    m = re.match(r"^\s*([A-Za-z0-9_.\-/]+)\s*[:=]\s*(.*?)\s*$", line)
    return (m.group(1), m.group(2).strip().strip('"')) if m else None


def parse_lines(lines: Iterable[str], aliases: dict[str, str]) -> dict[str, object]:
    values = {field: None for field in FIELDS}
    for line in lines:
        parsed = parse_line(line)
        if not parsed:
            continue
        key, value = parsed
        standard = aliases.get(normalize_key(key))
        if standard and values[standard] is None:
            values[standard] = value
    return values


def find_member(names: list[str], patterns: list[str]) -> str | None:
    matches = [n for n in names if any(fnmatch.fnmatch(n.lower(), p.lower()) for p in patterns)]
    return sorted(matches, key=lambda n: (n.count("/"), len(n)))[0] if matches else None


def from_zip(path: Path, patterns: list[str], aliases: dict[str, str]) -> dict | None:
    with zipfile.ZipFile(path, "r") as zf:
        member = find_member(zf.namelist(), patterns)
        if member is None:
            return None
        with zf.open(member, "r") as raw:
            values = parse_lines((b.decode("utf-8", errors="ignore") for b in raw), aliases)
        values.update(Source_Item=str(path), Metadata_File=member)
        return values


def from_folder(folder: Path, patterns: list[str], aliases: dict[str, str]) -> dict | None:
    candidates = [p for p in folder.rglob("*") if p.is_file() and any(fnmatch.fnmatch(p.name.lower(), x.lower()) for x in patterns)]
    if not candidates:
        return None
    metadata = sorted(candidates, key=lambda p: (len(p.relative_to(folder).parts), len(str(p))))[0]
    with metadata.open("r", encoding="utf-8", errors="ignore") as f:
        values = parse_lines(f, aliases)
    values.update(Source_Item=str(folder), Metadata_File=str(metadata.relative_to(folder)))
    return values


def status(row: pd.Series) -> str:
    missing = [f for f in FIELDS if pd.isna(row[f]) or row[f] == ""]
    return "OK" if not missing else "MISSING: " + ", ".join(missing)


def get_interactive_paths() -> tuple[Path, Path, Path]:
    """Prompts the user interactively in the console for input, output, and config paths."""
    print("=" * 60)
    print(" SATELLITE METADATA EXTRACTION TOOL (Interactive Mode)")
    print("=" * 60)

    # 1. Input directory prompt
    default_input = r"D:\satellite"
    raw_input = input(f"Enter input folder path [Default: {default_input}]: ").strip().strip('"')
    input_path = Path(raw_input if raw_input else default_input)

    # 2. Output Excel path prompt
    default_output = r"D:\Satellite\Satellite_Coordinates.xlsx"
    raw_output = input(f"Enter output Excel file path [Default: {default_output}]: ").strip().strip('"')
    output_path = Path(raw_output if raw_output else default_output)

    # 3. Config file path prompt
    default_config = r"config/example_metadata_aliases.json"
    raw_config = input(f"Enter config JSON path [Default: {default_config}]: ").strip().strip('"')
    config_path = Path(raw_config if raw_config else default_config)

    print("-" * 60)
    return input_path, output_path, config_path


def main() -> None:
    # Get paths via interactive user input
    input_path, output_path, config_path = get_interactive_paths()

    # Validate paths
    if not input_path.exists():
        raise SystemExit(f"Error: Input path does not exist: {input_path}")
    if not config_path.exists():
        raise SystemExit(f"Error: Config file does not exist: {config_path}")

    patterns, aliases = load_config(config_path)
    records: list[dict] = []
    seen_folders: set[Path] = set()

    print(f"Scanning for satellite metadata in: {input_path} ...")

    for path in sorted(input_path.rglob("*")):
        try:
            if path.is_file() and path.suffix.lower() == ".zip":
                record = from_zip(path, patterns, aliases)
                if record:
                    records.append(record)
            elif path.is_dir() and path not in seen_folders:
                record = from_folder(path, patterns, aliases)
                if record:
                    records.append(record)
                    seen_folders.add(path)
        except zipfile.BadZipFile:
            print(f"WARNING: invalid ZIP skipped: {path}")
        except OSError as exc:
            print(f"WARNING: could not read {path}: {exc}")
        except Exception as exc:
            print(f"WARNING: failed to process {path}: {exc}")

    if not records:
        raise SystemExit("No compatible metadata files were found. Check the input path and configuration.")

    df = pd.DataFrame(records)
    for field in FIELDS:
        df[field] = pd.to_numeric(df[field], errors="coerce")
    df["Extraction_Status"] = df.apply(status, axis=1)

    cols = ["Source_Item", "Metadata_File", *FIELDS, "Extraction_Status"]
    df = df[[c for c in cols if c in df.columns]]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_path, index=False)

    print("\nMetadata extraction completed.")
    print(f"Records written : {len(df):,}")
    print(f"Successful rows : {(df['Extraction_Status'] == 'OK').sum():,}")
    print(f"Output Excel    : {output_path}")


if __name__ == "__main__":
    main()