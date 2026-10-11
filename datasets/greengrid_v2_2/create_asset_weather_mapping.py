#!/usr/bin/env python3
"""Create asset_weather_mapping.csv for the GreenGrid Energy analysis pipeline.

This script uses an explicit, editable regional mapping assumption. It does not
claim to find the geographically nearest station unless coordinates and a
distance-based method are added.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import pandas as pd

ASSET_CANDIDATES = ["asset_registry_clean.csv", "asset_registry.csv", "asset_registry_raw.csv"]
WEATHER_CANDIDATES = ["weather_station_clean.csv", "weather_station.csv", "weather_station_raw.csv"]

# Edit these IDs to match station_id values in your cleaned weather file.
# These are example assumptions, not guaranteed IDs in your dataset.
DEFAULT_REGION_STATION_MAP = {
    "North": "WS-NORTH-01",
    "Central": "WS-CENTRAL-01",
}

def find_file(folder: Path, candidates: list[str]) -> Path:
    for name in candidates:
        p = folder / name
        if p.exists():
            return p
    raise FileNotFoundError(f"No input file found in {folder}. Tried: {candidates}")

def main() -> int:
    parser = argparse.ArgumentParser(description="Create an asset-to-weather-station mapping CSV.")
    parser.add_argument("--input-dir", default="clean_data", help="Folder containing asset and weather CSVs.")
    parser.add_argument("--output", default="asset_weather_mapping.csv", help="Output CSV path.")
    parser.add_argument("--template-only", action="store_true",
                        help="Create a blank mapping template for manual completion.")
    args = parser.parse_args()

    folder = Path(args.input_dir)
    try:
        assets_path = find_file(folder, ASSET_CANDIDATES)
        weather_path = find_file(folder, WEATHER_CANDIDATES)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    assets = pd.read_csv(assets_path)
    weather = pd.read_csv(weather_path)

    missing = {"asset_id", "region"} - set(assets.columns)
    if missing:
        print(f"ERROR: {assets_path.name} missing columns: {sorted(missing)}", file=sys.stderr)
        return 1
    if "station_id" not in weather.columns:
        print(f"ERROR: {weather_path.name} missing column: station_id", file=sys.stderr)
        return 1

    asset_inventory = (assets[["asset_id", "region"]].dropna().drop_duplicates()
                       .sort_values(["region", "asset_id"]))
    station_ids = sorted(weather["station_id"].dropna().astype(str).unique())

    print("\nAssets found:")
    print(asset_inventory.to_string(index=False))
    print("\nStation IDs found:")
    for sid in station_ids:
        print(f"  - {sid}")

    if args.template_only:
        mapping = asset_inventory[["asset_id"]].copy()
        mapping["station_id"] = ""
        mapping["mapping_method"] = "MANUAL_REVIEW_REQUIRED"
        mapping["mapping_confidence"] = "UNVERIFIED"
    else:
        missing_defaults = {region: sid for region, sid in DEFAULT_REGION_STATION_MAP.items()
                            if sid not in station_ids}
        if missing_defaults:
            print("\nERROR: Default station IDs do not exist in the weather file:", file=sys.stderr)
            for region, sid in missing_defaults.items():
                print(f"  {region}: {sid}", file=sys.stderr)
            print("Edit DEFAULT_REGION_STATION_MAP in this script, or use --template-only.", file=sys.stderr)
            return 2
        mapping = asset_inventory[["asset_id", "region"]].copy()
        mapping["station_id"] = mapping["region"].map(DEFAULT_REGION_STATION_MAP)
        mapping["mapping_method"] = "ASSUMPTION_REGION_REPRESENTATIVE_STATION"
        mapping["mapping_confidence"] = "ASSUMPTION"

    if mapping["asset_id"].duplicated().any():
        print("ERROR: More than one mapping row per asset.", file=sys.stderr)
        return 1
    if not args.template_only:
        unknown = sorted(set(mapping["station_id"].dropna()) - set(station_ids))
        if unknown:
            print(f"ERROR: Unknown station IDs in mapping: {unknown}", file=sys.stderr)
            return 1

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    mapping.to_csv(out, index=False)
    print(f"\nCreated: {out.resolve()}")
    print(f"Mappings: {len(mapping)}")
    print("Review this assumption-based mapping before analysis.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
