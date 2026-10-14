#!/usr/bin/env python3
"""GreenGrid Energy: build an analysis-ready asset-hour table from cleaned CSVs.

Expected cleaned source files (accepted aliases are resolved automatically):
  asset_registry_clean.csv, scada_generation_clean.csv,
  ems_operations_clean.csv, bess_operations_clean.csv,
  weather_station_clean.csv, market_price_clean.csv,
  dispatch_curtailment_log_clean.csv

Optional weather mapping CSV columns: asset_id, station_id. If there is exactly
one weather station, it is mapped to all assets automatically. If there are
multiple stations, a mapping file is required to prevent row multiplication.

Important: source SCADA has availability, not metered actual generation. This
script therefore computes a transparent *modeled* generation/curtailment view.
It does not claim these are measured actual output or settlement revenue.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import numpy as np
import pandas as pd

FILES = {
    "assets": ["asset_registry_clean.csv", "asset_registry.csv", "asset_registry_raw.csv"],
    "scada": ["scada_generation_clean.csv", "scada_generation.csv", "scada_generation_raw.csv"],
    "ems": ["ems_operations_clean.csv", "ems_operations.csv", "ems_operations_raw.csv"],
    "bess": ["bess_operations_clean.csv", "bess_operations.csv", "bess_operations_raw.csv"],
    "weather": ["weather_station_clean.csv", "weather_station.csv", "weather_station_raw.csv"],
    "market": ["market_price_clean.csv", "market_price.csv", "market_price_raw.csv"],
    "dispatch": ["dispatch_curtailment_log_clean.csv", "dispatch_curtailment_log.csv", "dispatch_curtailment_log_raw.csv"],
}

REGION_SHARES = {"North": 0.45, "Central": 0.55}
CHARGE_EFFICIENCY = 0.94
DISCHARGE_EFFICIENCY = 0.92
INITIAL_SOC_MWH = {"North": 170.0, "Central": 150.0}


def find_file(folder: Path, candidates: list[str], label: str) -> Path:
    for name in candidates:
        p = folder / name
        if p.exists():
            return p
    raise FileNotFoundError(
        f"Cannot find {label} file in {folder}. Expected one of: {', '.join(candidates)}"
    )


def read_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    # Remove accidental whitespace in column names; do not silently rename semantics.
    df.columns = [str(c).strip() for c in df.columns]
    return df


def require_columns(df: pd.DataFrame, columns: list[str], table: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{table} is missing required columns: {missing}")


def normalize_timestamp(df: pd.DataFrame, col: str, table: str) -> pd.DataFrame:
    require_columns(df, [col], table)
    out = df.copy()
    out[col] = pd.to_datetime(out[col], errors="coerce")
    bad = int(out[col].isna().sum())
    if bad:
        raise ValueError(f"{table}.{col} has {bad} missing/invalid timestamps. Fix during cleaning first.")
    return out


def numeric(df: pd.DataFrame, cols: list[str], table: str, allow_null: bool = False) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col not in out.columns:
            continue
        out[col] = pd.to_numeric(out[col], errors="coerce")
        if not allow_null and out[col].isna().any():
            raise ValueError(f"{table}.{col} contains null/non-numeric values; clean these before modeling.")
    return out


def assert_unique(df: pd.DataFrame, keys: list[str], table: str) -> None:
    dup = df.duplicated(keys, keep=False)
    if dup.any():
        examples = df.loc[dup, keys].head(5).to_dict("records")
        raise ValueError(
            f"{table} is not unique at grain {keys}; {int(dup.sum())} duplicate rows. "
            f"Resolve duplicates before joining. Examples: {examples}"
        )


def make_weather_mapping(assets: pd.DataFrame, weather: pd.DataFrame, mapping_path: Path | None) -> pd.DataFrame:
    if mapping_path:
        mapping = read_csv(mapping_path)
        require_columns(mapping, ["asset_id", "station_id"], "weather mapping")
        mapping = mapping[["asset_id", "station_id"]].drop_duplicates()
    else:
        stations = weather["station_id"].dropna().astype(str).unique().tolist()
        if len(stations) != 1:
            raise ValueError(
                f"Weather data contains {len(stations)} stations ({stations[:8]}). "
                "Provide --weather-mapping CSV with columns asset_id,station_id. "
                "Joining on timestamp alone would multiply rows."
            )
        mapping = assets[["asset_id"]].copy()
        mapping["station_id"] = stations[0]

    unknown_assets = set(mapping["asset_id"]) - set(assets["asset_id"])
    unknown_stations = set(mapping["station_id"]) - set(weather["station_id"].astype(str))
    if unknown_assets or unknown_stations:
        raise ValueError(f"Weather mapping has unknown assets={sorted(unknown_assets)} or stations={sorted(unknown_stations)}")
    counts = mapping.groupby("asset_id")["station_id"].nunique()
    missing = set(assets["asset_id"]) - set(counts.index)
    multiple = counts[counts != 1]
    if missing or not multiple.empty:
        raise ValueError(f"Each asset must map to exactly one station. Missing assets={sorted(missing)}, invalid mappings={multiple.to_dict()}")
    return mapping


def wind_capacity_factor(speed: pd.Series) -> pd.Series:
    # Same piecewise proxy used by the generator's wind model.
    s = speed.astype(float)
    cf = np.select(
        [s < 3, s < 12, s < 16, s >= 16],
        [0.0, ((s - 3) / 9) ** 3 * 0.92, 0.92, 0.20],
    )
    return pd.Series(np.clip(cf, 0, 0.95), index=s.index)


def build_bess_features(bess: pd.DataFrame) -> pd.DataFrame:
    require_columns(bess, ["timestamp", "region", "battery_power_capacity_mw", "battery_energy_capacity_mwh", "charge_mwh", "discharge_mwh"], "BESS")
    b = normalize_timestamp(bess, "timestamp", "BESS")
    b["region"] = b["region"].astype(str).str.strip().str.title()
    b = numeric(b, ["battery_power_capacity_mw", "battery_energy_capacity_mwh", "charge_mwh", "discharge_mwh"], "BESS")
    assert_unique(b, ["timestamp", "region"], "BESS")
    b = b.sort_values(["region", "timestamp"]).copy()
    b["soc_mwh_reconstructed"] = np.nan
    for region, idx in b.groupby("region", sort=False).groups.items():
        soc = INITIAL_SOC_MWH.get(region, float(b.loc[idx[0], "battery_energy_capacity_mwh"]) / 2)
        cap = float(b.loc[idx[0], "battery_energy_capacity_mwh"])
        vals = []
        for row_idx in idx:
            charge = float(b.at[row_idx, "charge_mwh"])
            discharge = float(b.at[row_idx, "discharge_mwh"])
            soc = soc + charge * CHARGE_EFFICIENCY - discharge / DISCHARGE_EFFICIENCY
            # Retain physical bounds but expose the resulting value as reconstructed, not metered.
            soc = float(np.clip(soc, 0, cap))
            vals.append((row_idx, soc))
        for row_idx, value in vals:
            b.at[row_idx, "soc_mwh_reconstructed"] = value
    return b


def expand_dispatch_events(dispatch: pd.DataFrame) -> pd.DataFrame:
    columns = ["timestamp", "region", "dispatch_event_count", "dispatch_event_ids", "dispatch_reasons"]
    if dispatch.empty:
        return pd.DataFrame(columns=columns)
    require_columns(dispatch, ["region", "start_time", "end_time"], "dispatch log")
    d = normalize_timestamp(dispatch, "start_time", "dispatch log")
    d = normalize_timestamp(d, "end_time", "dispatch log")
    d["region"] = d["region"].astype(str).str.strip().str.title()
    if (d["end_time"] < d["start_time"]).any():
        raise ValueError("Dispatch log has end_time earlier than start_time.")
    rows = []
    for _, event in d.iterrows():
        # Event start/end are treated as inclusive hourly timestamps.
        hours = pd.date_range(event["start_time"].floor("h"), event["end_time"].floor("h"), freq="h")
        for ts in hours:
            rows.append({
                "timestamp": ts,
                "region": event["region"],
                "event_id": str(event.get("event_id", "UNKNOWN")),
                "reason": str(event.get("reason", "Unknown")),
            })
    if not rows:
        return pd.DataFrame(columns=columns)
    expanded = pd.DataFrame(rows)
    agg = expanded.groupby(["timestamp", "region"], as_index=False).agg(
        dispatch_event_count=("event_id", "nunique"),
        dispatch_event_ids=("event_id", lambda s: "|".join(sorted(set(s)))),
        dispatch_reasons=("reason", lambda s: "|".join(sorted(set(s)))),
    )
    return agg


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("clean_data"), help="Folder containing cleaned CSV files (default: ./clean_data)")
    parser.add_argument("--output-dir", type=Path, default=Path("analysis_output"), help="Output folder (default: ./analysis_output)")
    parser.add_argument("--weather-mapping", type=Path, default=None, help="Optional CSV mapping assets to weather stations: asset_id,station_id")
    parser.add_argument("--interval-hours", type=float, default=1.0, help="Length of each observation interval in hours (default 1)")
    args = parser.parse_args()
    if args.interval_hours <= 0:
        raise ValueError("--interval-hours must be greater than zero.")

    paths = {k: find_file(args.input_dir, names, k) for k, names in FILES.items()}
    assets = read_csv(paths["assets"])
    scada = read_csv(paths["scada"])
    ems = read_csv(paths["ems"])
    bess = read_csv(paths["bess"])
    weather = read_csv(paths["weather"])
    market = read_csv(paths["market"])
    dispatch = read_csv(paths["dispatch"])

    require_columns(assets, ["asset_id", "asset_name", "technology", "region", "capacity_mw"], "asset registry")
    require_columns(scada, ["timestamp", "asset_id", "capacity_mw", "availability_pct"], "SCADA")
    require_columns(weather, ["timestamp", "station_id", "solar_irradiance_index", "wind_speed_mps"], "weather")
    require_columns(ems, ["timestamp", "north_export_limit_mw", "central_export_limit_mw"], "EMS")
    require_columns(market, ["timestamp", "market_price_usd_per_mwh"], "market price")

    assets["asset_id"] = assets["asset_id"].astype(str).str.strip()
    assets["region"] = assets["region"].astype(str).str.strip().str.title()
    assets["technology"] = assets["technology"].astype(str).str.strip()
    assert_unique(assets, ["asset_id"], "asset registry")

    scada = normalize_timestamp(scada, "timestamp", "SCADA")
    scada["asset_id"] = scada["asset_id"].astype(str).str.strip()
    scada = numeric(scada, ["capacity_mw", "availability_pct"], "SCADA")
    assert_unique(scada, ["timestamp", "asset_id"], "SCADA")
    scada["availability_factor"] = scada["availability_pct"] / 100.0
    if ((scada["availability_factor"] < 0) | (scada["availability_factor"] > 1.05)).any():
        raise ValueError("SCADA availability_pct is outside expected range 0–105%; inspect cleaned data.")

    weather = normalize_timestamp(weather, "timestamp", "weather")
    weather["station_id"] = weather["station_id"].astype(str).str.strip()
    weather = numeric(weather, ["solar_irradiance_index", "wind_speed_mps"], "weather")
    assert_unique(weather, ["timestamp", "station_id"], "weather")
    mapping = make_weather_mapping(assets, weather, args.weather_mapping)

    ems = normalize_timestamp(ems, "timestamp", "EMS")
    ems = numeric(ems, ["north_export_limit_mw", "central_export_limit_mw"], "EMS")
    has_regional_demand = (
        "north_demand_mwh" in ems.columns
        and "central_demand_mwh" in ems.columns
    )
    if has_regional_demand:
        ems = numeric(ems, ["north_demand_mwh", "central_demand_mwh"], "EMS")
        regional_total = ems["north_demand_mwh"] + ems["central_demand_mwh"]
        if "total_demand_mwh" not in ems.columns:
            ems["total_demand_mwh"] = regional_total
        else:
            ems = numeric(
                ems,
                ["total_demand_mwh"],
                "EMS",
                allow_null=True,
            )
            missing_total = ems["total_demand_mwh"].isna()
            if missing_total.any():
                print(
                    f"WARNING: EMS total_demand_mwh is missing for {int(missing_total.sum())} rows; "
                    "deriving it from North and Central demand.",
                    file=sys.stderr,
                )
                ems.loc[missing_total, "total_demand_mwh"] = regional_total[missing_total]
    else:
        require_columns(ems, ["total_demand_mwh"], "EMS")
        ems = numeric(ems, ["total_demand_mwh"], "EMS")
        ems["north_demand_mwh"] = ems["total_demand_mwh"] * REGION_SHARES["North"]
        ems["central_demand_mwh"] = ems["total_demand_mwh"] * REGION_SHARES["Central"]
        print("WARNING: EMS regional demand columns absent; using documented 45% North / 55% Central allocation.", file=sys.stderr)
    assert_unique(ems, ["timestamp"], "EMS")
    demand_error = (ems["north_demand_mwh"] + ems["central_demand_mwh"] - ems["total_demand_mwh"]).abs()
    if (demand_error > 1e-4 + 1e-12).any():
        raise ValueError("Regional demand does not reconcile to total_demand_mwh. Check EMS data/allocation assumptions.")

    market = normalize_timestamp(market, "timestamp", "market price")
    market = numeric(market, ["market_price_usd_per_mwh"], "market price")
    assert_unique(market, ["timestamp"], "market price")

    # Join weather to SCADA only after an explicit asset-to-station mapping.
    weather = weather.merge(mapping, on="station_id", how="inner", validate="many_to_many")
    if "region" in scada.columns:
        scada["region"] = scada["region"].astype(str).str.strip().str.title()
        registry_region = scada["asset_id"].map(assets.set_index("asset_id")["region"])
        mismatch = registry_region.notna() & scada["region"].ne(registry_region)
        if mismatch.any():
            mismatch_count = scada.loc[mismatch, "asset_id"].nunique()
            examples = (
                scada.loc[mismatch, ["asset_id", "region"]]
                .drop_duplicates()
                .head(5)
                .to_dict("records")
            )
            print(
                f"WARNING: SCADA region conflicts with the asset registry for "
                f"{mismatch_count} assets; using registry regions. Examples: {examples}",
                file=sys.stderr,
            )
        scada = scada.drop(columns="region")
    base = scada.merge(assets.drop(columns=["capacity_mw"], errors="ignore"), on="asset_id", how="left", validate="many_to_one")
    if base["region"].isna().any():
        raise ValueError("Some SCADA asset_id values do not exist in asset registry.")
    base = base.merge(weather, on=["timestamp", "asset_id"], how="left", validate="one_to_one", suffixes=("", "_weather"))
    if base["solar_irradiance_index"].isna().any() or base["wind_speed_mps"].isna().any():
        missing = int(base["solar_irradiance_index"].isna().sum())
        raise ValueError(f"Weather mapping/join left {missing} asset-hour rows without weather data.")
    if not base["region"].isin(["North", "Central"]).all():
        unknown_regions = sorted(set(base.loc[~base["region"].isin(["North", "Central"]), "region"]))
        raise ValueError(f"Asset registry contains unsupported regions: {unknown_regions}")

    # Transparent potential-generation estimate; weather model is a proxy, not exact reconstruction of generator RNG.
    is_solar = base["technology"].str.lower().str.contains("solar")
    solar_cf = np.clip(base["solar_irradiance_index"].astype(float) * 0.97, 0, 1)
    wind_cf = wind_capacity_factor(base["wind_speed_mps"])
    base["modeled_capacity_factor"] = np.where(is_solar, solar_cf, wind_cf)

    # Potensial generation formula
    base["potential_generation_mwh"] = (
        base["capacity_mw"] * base["modeled_capacity_factor"] * base["availability_factor"] * args.interval_hours
    )

    # Allocate regional operating quantities onto the asset-hour rows.
    region_keys = ["timestamp", "region"]
    region_groups = base.groupby(region_keys, sort=False)
    region_potential = region_groups["potential_generation_mwh"].transform("sum")
    region_capacity = region_groups["capacity_mw"].transform("sum")
    base["asset_generation_share_within_region"] = np.where(
        region_potential > 0,
        base["potential_generation_mwh"] / region_potential,
        base["capacity_mw"] / region_capacity,
    )

    ems_columns = [
        "timestamp",
        "north_demand_mwh",
        "central_demand_mwh",
        "north_export_limit_mw",
        "central_export_limit_mw",
    ]
    base = base.merge(
        ems[ems_columns],
        on="timestamp",
        how="left",
        validate="many_to_one",
    )
    bess_features = build_bess_features(bess)
    base = base.merge(
        bess_features[
            [
                "timestamp",
                "region",
                "battery_power_capacity_mw",
                "battery_energy_capacity_mwh",
                "charge_mwh",
                "discharge_mwh",
                "soc_mwh_reconstructed",
            ]
        ],
        on=region_keys,
        how="left",
        validate="many_to_one",
    )
    ems_bess_columns = [
        "north_demand_mwh",
        "central_demand_mwh",
        "north_export_limit_mw",
        "central_export_limit_mw",
        "battery_power_capacity_mw",
        "battery_energy_capacity_mwh",
        "charge_mwh",
        "discharge_mwh",
        "soc_mwh_reconstructed",
    ]
    missing_coverage = base[ems_bess_columns].isna().any(axis=1)
    if missing_coverage.any():
        sample = base.loc[missing_coverage, ["timestamp", "region"]].drop_duplicates().head(5).to_dict("records")
        raise ValueError(
            f"EMS/BESS coverage is incomplete for {int(missing_coverage.sum())} asset-hour rows. "
            f"Examples: {sample}"
        )

    base["asset_demand_mwh"] = np.where(
        base["region"] == "North",
        base["north_demand_mwh"],
        base["central_demand_mwh"],
    ) * base["asset_generation_share_within_region"]
    base["asset_export_capacity_mwh"] = np.where(
        base["region"] == "North",
        base["north_export_limit_mw"],
        base["central_export_limit_mw"],
    ) * args.interval_hours * base["asset_generation_share_within_region"]
    for source, target in [
        ("battery_power_capacity_mw", "asset_battery_power_capacity_mw"),
        ("battery_energy_capacity_mwh", "asset_battery_energy_capacity_mwh"),
        ("charge_mwh", "asset_battery_charge_mwh"),
        ("discharge_mwh", "asset_battery_discharge_mwh"),
        ("soc_mwh_reconstructed", "asset_battery_soc_mwh"),
    ]:
        base[target] = base[source] * base["asset_generation_share_within_region"]
    base["asset_absorption_capacity_mwh"] = (
        base["asset_demand_mwh"]
        + base["asset_export_capacity_mwh"]
        + base["asset_battery_charge_mwh"]
    )
    region_absorption = base.groupby(region_keys, sort=False)[
        "asset_absorption_capacity_mwh"
    ].transform("sum")
    base["asset_curtailment_mwh"] = (
        np.maximum(region_potential - region_absorption, 0)
        * base["asset_generation_share_within_region"]
    )
    base["asset_actual_generation_mwh"] = np.maximum(
        base["potential_generation_mwh"] - base["asset_curtailment_mwh"], 0
    )
    base["asset_curtailment_rate_pct"] = np.where(
        base["potential_generation_mwh"] > 0,
        base["asset_curtailment_mwh"] / base["potential_generation_mwh"] * 100,
        0.0,
    )
    base["asset_surplus_mwh"] = (
        np.maximum(
            region_potential
            - np.where(
                base["region"] == "North",
                base["north_demand_mwh"],
                base["central_demand_mwh"],
            ),
            0,
        )
        * base["asset_generation_share_within_region"]
    )
    base["asset_battery_net_energy_mwh"] = (
        base["asset_battery_discharge_mwh"] - base["asset_battery_charge_mwh"]
    )

    # Allocate portfolio-wide quantities across assets without a separate hourly table.
    hour_groups = base.groupby("timestamp", sort=False)
    hour_potential = hour_groups["potential_generation_mwh"].transform("sum")
    hour_capacity = hour_groups["capacity_mw"].transform("sum")
    base["asset_generation_share_within_portfolio"] = np.where(
        hour_potential > 0,
        base["potential_generation_mwh"] / hour_potential,
        base["capacity_mw"] / hour_capacity,
    )

    market = market[["timestamp", "market_price_usd_per_mwh"]].copy()
    base = base.merge(market, on="timestamp", how="left", validate="many_to_one")
    if base["market_price_usd_per_mwh"].isna().any():
        missing = int(base["market_price_usd_per_mwh"].isna().sum())
        raise ValueError(f"Market price missing for {missing} asset-hour rows.")

    asset_demand = base.groupby("timestamp", sort=False)["asset_demand_mwh"].transform("sum")
    asset_actual = base.groupby("timestamp", sort=False)["asset_actual_generation_mwh"].transform("sum")
    asset_curtailment = base.groupby("timestamp", sort=False)["asset_curtailment_mwh"].transform("sum")
    base["asset_potential_surplus_mwh"] = np.maximum(
        hour_potential - asset_demand, 0
    ) * base["asset_generation_share_within_portfolio"]
    base["asset_actual_surplus_mwh"] = np.maximum(
        asset_actual - asset_demand, 0
    ) * base["asset_generation_share_within_portfolio"]
    base["asset_net_load_mwh"] = (
        asset_demand - asset_actual
    ) * base["asset_generation_share_within_portfolio"]
    base["asset_renewable_share_pct"] = np.where(
        base["asset_demand_mwh"] > 0,
        base["asset_actual_generation_mwh"] / base["asset_demand_mwh"] * 100,
        np.nan,
    )
    hourly_potential_surplus = base.groupby("timestamp", sort=False)[
        "asset_potential_surplus_mwh"
    ].transform("sum")
    stress_flag = ((asset_curtailment > 50) | (hourly_potential_surplus > 100)).astype(int)
    asset_count_per_hour = base.groupby("timestamp", sort=False)[
        "asset_id"
    ].transform("nunique")
    base["asset_stress_hour_allocation"] = stress_flag / asset_count_per_hour
    negative_price_flag = (base["market_price_usd_per_mwh"] < 0).astype(int)
    base["asset_negative_price_hour_allocation"] = (
        negative_price_flag / asset_count_per_hour
    )
    # Indicative value proxies only; actual settlement/revenue requires contract and market rules.
    base["asset_curtailment_value_usd"] = (
        base["asset_curtailment_mwh"] * base["market_price_usd_per_mwh"]
    )
    base["asset_generation_market_value_usd"] = (
        base["asset_actual_generation_mwh"] * base["market_price_usd_per_mwh"]
    )
    base["asset_curtailment_value_positive_price_usd"] = np.where(
        base["market_price_usd_per_mwh"] > 0,
        base["asset_curtailment_value_usd"],
        0.0,
    )
    base["asset_curtailment_value_at_negative_price_usd"] = np.where(
        base["market_price_usd_per_mwh"] < 0,
        base["asset_curtailment_value_usd"],
        0.0,
    )

    # Expand dispatch events to region-hour and attach their context to each asset-hour row.
    event_hour = expand_dispatch_events(dispatch)
    base = base.merge(
        event_hour,
        on=region_keys,
        how="left",
        validate="many_to_one",
    )
    base["asset_dispatch_event_count"] = (
        base["dispatch_event_count"].fillna(0)
        * base["asset_generation_share_within_region"]
    )
    base["asset_dispatch_event_ids"] = base["dispatch_event_ids"].fillna("")
    base["asset_dispatch_reasons"] = base["dispatch_reasons"].fillna("")
    base = base.drop(
        columns=[
            "north_demand_mwh",
            "central_demand_mwh",
            "north_export_limit_mw",
            "central_export_limit_mw",
            "battery_power_capacity_mw",
            "battery_energy_capacity_mwh",
            "charge_mwh",
            "discharge_mwh",
            "soc_mwh_reconstructed",
            "dispatch_event_count",
            "dispatch_event_ids",
            "dispatch_reasons",
        ]
    )
    # Clean output ordering: identifiers, source data, and asset-level metrics.
    first = [c for c in ["timestamp", "asset_id", "asset_name", "technology", "region", "grid_node", "capacity_mw", "availability_pct", "availability_factor", "station_id", "solar_irradiance_index", "wind_speed_mps", "temperature_c"] if c in base.columns]
    base = base[first + [c for c in base.columns if c not in first]]
    base = base.sort_values(["timestamp", "region", "asset_id"]).reset_index(drop=True)

    # Validation: no row multiplication and energy identities reconcile within model.
    expected_rows = len(scada)
    if len(base) != expected_rows:
        raise AssertionError(f"Join changed SCADA row count: expected {expected_rows}, got {len(base)}")
    assert_unique(base, ["timestamp", "asset_id"], "final asset-hour table")
    if (base["asset_curtailment_mwh"] - (base["potential_generation_mwh"] - base["asset_actual_generation_mwh"])).abs().max() > 1e-6:
        raise AssertionError("Asset generation-curtailment identity failed.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    main_out = args.output_dir / "greengrid_asset_hour_analysis_v2.csv"
    base.to_csv(main_out, index=False)

    print("SUCCESS: GreenGrid asset-hour analysis table created")
    print(f"Main asset-hour table : {main_out} ({len(base):,} rows)")
    print("\nModeled summary (not metered actuals):")
    print(f"Potential generation : {base['potential_generation_mwh'].sum():,.2f} MWh")
    print(f"Potential generation : {base['potential_generation_mwh'].sum():,.2f} MWh")
    print(f"Modeled actual output: {base['asset_actual_generation_mwh'].sum():,.2f} MWh")
    print(f"Modeled curtailment  : {base['asset_curtailment_mwh'].sum():,.2f} MWh")
    print(f"Curtailment rate     : {base['asset_curtailment_mwh'].sum() / max(base['potential_generation_mwh'].sum(), 1e-9) * 100:.3f}%")
    print(f"Potential surplus    : {base['asset_potential_surplus_mwh'].sum():,.2f} MWh")
    print(f"Negative-price hours : {int(round(base['asset_negative_price_hour_allocation'].sum())):,}")
    print(f"Indicative curtailment value (signed): ${base['asset_curtailment_value_usd'].sum():,.2f}")
    print("NOTE: market-price products are indicative value proxies, not booked revenue or guaranteed lost revenue.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
