"""
GreenGrid Energy — Renewable Curtailment & Energy Surplus
Synthetic Operational Data Generator — Version 2.1

BUSINESS SCENARIO
-----------------
GreenGrid Energy operates solar and wind assets connected to a constrained
electricity grid. The Energy Management team wants to understand renewable
energy surplus and curtailment, identify operational drivers, and quantify
potential mitigation opportunities.

DATA SOURCES SIMULATED
----------------------
1. Asset Master          -> asset_registry_raw.csv
2. SCADA Generation      -> scada_generation_raw.csv
3. EMS Demand/Grid       -> ems_operations_raw.csv
4. BESS Controller       -> bess_operations_raw.csv
5. Weather Stations      -> weather_station_raw.csv
6. Market Feed           -> market_price_raw.csv
7. Dispatch Log          -> dispatch_curtailment_log_raw.csv

RAW DATA DESIGN
---------------
The generator first creates a CLEAN operational truth using explicit business
rules. It then creates RAW extracts by injecting realistic data-quality issues.

Therefore:
    RAW data       = what the analyst receives
    CLEAN truth    = reconciliation benchmark
    BUSINESS LOGIC = physically/business-consistent relationships

IMPORTANT CONCEPTS
------------------
Potential generation
    Energy the asset could produce based on resource and availability.

Actual generation
    Energy actually produced after dispatch/system constraints.

Curtailment
    Potential generation - actual generation.

Potential surplus
    max(Potential renewable generation - demand, 0)

Actual surplus
    max(Actual renewable generation - demand, 0)

A high-surplus condition does NOT automatically mean all surplus becomes
curtailment because energy can be absorbed by demand, export capacity, or BESS.

DATA-QUALITY ISSUES INTENTIONALLY INJECTED
------------------------------------------
- duplicate SCADA records
- missing readings
- inconsistent categorical capitalization
- whitespace
- mixed timestamp formats
- numeric values stored as strings
- impossible BESS SOC values
- invalid negative weather values
- unit-label inconsistencies
- duplicated dispatch events
- missing dispatch reason
- stale/late records
- a small number of physically implausible generation readings

The issues are deliberately limited so that the underlying business signal
remains recoverable.

OUTPUT
------
greengrid_v2_1/
├── raw_data/
│   ├── asset_registry_raw.csv
│   ├── scada_generation_raw.csv
│   ├── ems_operations_raw.csv
│   ├── bess_operations_raw.csv
│   ├── weather_station_raw.csv
│   ├── market_price_raw.csv
│   └── dispatch_curtailment_log_raw.csv
│
├── reference/
│   ├── clean_truth_hourly.csv
│   ├── expected_kpis.csv
│   └── data_quality_issue_log.csv
│
└── metadata/
    └── README_generator.txt

The reference folder should be treated as validation material, not as the
analysis dataset.
"""

from pathlib import Path
import numpy as np
import pandas as pd


# ============================================================
# 1. CONFIGURATION
# ============================================================

SEED = 42
START = "2025-01-01 00:00:00"
END = "2025-12-31 23:00:00"

rng = np.random.default_rng(SEED)

BASE_DIR = Path("datasets/greengrid_v2_1")
RAW_DIR = BASE_DIR / "raw_data"
REF_DIR = BASE_DIR / "reference"
META_DIR = BASE_DIR / "metadata"

for folder in [RAW_DIR, REF_DIR, META_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

timestamps = pd.date_range(START, END, freq="h")
hours = timestamps.hour.to_numpy()
days = timestamps.dayofyear.to_numpy()
weekdays = timestamps.dayofweek.to_numpy()
n_hours = len(timestamps)

print(f"Generating {n_hours:,} hourly timestamps...")


# ============================================================
# 2. ASSET REGISTRY
# ============================================================

assets = pd.DataFrame([
    ["SOL-N01", "North Solar One", "Solar PV", "North", "NORTH_A", 180],
    ["SOL-N02", "North Solar Two", "Solar PV", "North", "NORTH_A", 140],
    ["WND-N01", "North Wind One", "Wind", "North", "NORTH_B", 220],
    ["SOL-C01", "Central Solar One", "Solar PV", "Central", "CENTRAL_A", 160],
    ["SOL-C02", "Central Solar Two", "Solar PV", "Central", "CENTRAL_A", 110],
    ["WND-C01", "Central Wind One", "Wind", "Central", "CENTRAL_B", 180],
], columns=[
    "asset_id",
    "asset_name",
    "technology",
    "region",
    "grid_node",
    "capacity_mw",
])

assets["commission_date"] = pd.to_datetime([
    "2023-06-01",
    "2024-03-15",
    "2022-10-01",
    "2023-01-10",
    "2024-07-01",
    "2022-05-20",
])

assets["asset_status"] = "Operational"


# ============================================================
# 3. WEATHER STATION DATA
# ============================================================
# Weather is generated first because renewable potential depends on resource.

# Solar irradiance:
# daylight curve + seasonality + cloud events + noise.
solar_day_curve = np.clip(
    1 - ((hours - 12) / 6) ** 2,
    0,
    None
)

solar_season = (
    0.92
    + 0.08 * np.cos(2 * np.pi * (days - 172) / 365)
)

cloud_factor = np.clip(
    0.93 + rng.normal(0, 0.10, n_hours),
    0.30,
    1.05
)

# Persistent cloudy periods.
cloud_event = rng.random(n_hours) < 0.04
cloud_factor = np.where(
    cloud_event,
    np.clip(rng.normal(0.48, 0.12, n_hours), 0.15, 0.75),
    cloud_factor
)

irradiance = np.clip(
    solar_day_curve * solar_season * cloud_factor,
    0,
    1.05
)

# Wind:
wind_speed = (
    7.0
    + 1.3 * np.sin(2 * np.pi * (days - 40) / 365)
    + 1.0 * np.sin(2 * np.pi * hours / 24 + 1.2)
    + rng.normal(0, 1.3, n_hours)
)
wind_speed = np.clip(wind_speed, 1.0, 16.0)

temperature = (
    27
    + 3.5 * np.sin(2 * np.pi * (hours - 14) / 24)
    + 1.8 * np.sin(2 * np.pi * days / 365)
    + rng.normal(0, 1.2, n_hours)
)

weather = pd.DataFrame({
    "timestamp": timestamps,
    "station_id": "WX-MASTER",
    "solar_irradiance_index": np.round(irradiance, 4),
    "wind_speed_mps": np.round(wind_speed, 3),
    "temperature_c": np.round(temperature, 2),
    "cloud_cover_pct": np.round(
        np.clip((1 - cloud_factor) * 100, 0, 100), 1
    ),
})


# ============================================================
# 4. ASSET AVAILABILITY / MAINTENANCE
# ============================================================
# A clean operational status table is created internally.
# It will be embedded in SCADA generation records.

availability = {}

for _, asset in assets.iterrows():

    values = np.clip(
        rng.normal(0.985, 0.008, n_hours),
        0.94,
        1.0
    )

    # Planned maintenance blocks.
    for _ in range(3):
        start_idx = rng.integers(0, n_hours - 48)
        duration = int(rng.integers(8, 36))
        values[start_idx:start_idx + duration] *= rng.uniform(
            0.05, 0.35
        )

    availability[asset.asset_id] = values


# ============================================================
# 5. POTENTIAL GENERATION — CLEAN TRUTH
# ============================================================

generation_rows = []

def solar_capacity_factor(irr):
    return np.clip(
        irr * rng.normal(0.97, 0.015, len(irr)),
        0,
        1
    )

def wind_capacity_factor(speed):
    cf = np.select(
        [
            speed < 3,
            speed < 12,
            speed < 16,
            speed >= 16,
        ],
        [
            0,
            ((speed - 3) / 9) ** 3 * 0.92,
            0.92,
            0.20,
        ]
    )
    return np.clip(cf, 0, 0.95)


for _, asset in assets.iterrows():

    if asset.technology == "Solar PV":
        cf = solar_capacity_factor(irradiance)
    else:
        cf = wind_capacity_factor(wind_speed)

    potential = (
        asset.capacity_mw
        * cf
        * availability[asset.asset_id]
    )

    for i, ts in enumerate(timestamps):
        generation_rows.append({
            "timestamp": ts,
            "asset_id": asset.asset_id,
            "capacity_mw": asset.capacity_mw,
            "availability_pct": availability[asset.asset_id][i] * 100,
            "capacity_factor": cf[i],
            "potential_generation_mwh": potential[i],
        })

potential_generation = pd.DataFrame(generation_rows)


# ============================================================
# 6. EMS DEMAND
# ============================================================

# Demand profile:
# - weekday > weekend
# - morning peak
# - evening peak
# - moderate midday demand
# - seasonal variation

morning_peak = 95 * np.exp(-((hours - 8) / 2.7) ** 2)
evening_peak = 170 * np.exp(-((hours - 19) / 3.0) ** 2)
midday_load = 65 * np.exp(-((hours - 13) / 4.5) ** 2)

weekday_multiplier = np.where(
    weekdays < 5,
    1.0,
    0.82
)

season_multiplier = (
    1
    + 0.07 * np.sin(2 * np.pi * (days - 30) / 365)
)

demand = (
    310
    + morning_peak
    + evening_peak
    + midday_load
) * weekday_multiplier * season_multiplier

# Random operational fluctuation.
demand += rng.normal(0, 14, n_hours)

# Deliberately create some low-demand weekend midday periods.
weekend_midday = (
    (weekdays >= 5)
    & (hours >= 10)
    & (hours <= 15)
    & (rng.random(n_hours) < 0.35)
)

demand[weekend_midday] *= rng.uniform(
    0.82,
    0.93,
    weekend_midday.sum()
)

demand = np.clip(demand, 180, None)


# ============================================================
# 7. GRID CAPACITY / CONSTRAINTS
# ============================================================

# Export limit by region.
# North is intentionally generation-heavy and transmission-constrained.
# The lower export headroom is the primary structural driver of curtailment.
north_limit = np.full(n_hours, 80.0)
central_limit = np.full(n_hours, 220.0)

# Scheduled / forced transmission constraints.
constraint_events = []

for region, limit in [
    ("North", north_limit),
    ("Central", central_limit),
]:
    for event_no in range(16):

        start_idx = int(rng.integers(0, n_hours - 12))
        duration = int(rng.integers(2, 12))

        reduction = rng.choice(
            [0.72, 0.82, 0.90],
            p=[0.25, 0.50, 0.25]
        )

        limit[start_idx:start_idx + duration] *= reduction

        constraint_events.append({
            "region": region,
            "start_time": timestamps[start_idx],
            "end_time": timestamps[
                min(start_idx + duration - 1, n_hours - 1)
            ],
            "normal_limit_mw": 80 if region == "North" else 220,
            "constrained_limit_mw": (
                (80 if region == "North" else 220) * reduction
            ),
        })

# North is deliberately more constrained during high-solar months,
# reinforcing the midday renewable bottleneck.
north_solar_constraint = (
    (hours >= 10)
    & (hours <= 15)
    & (days >= 90)
    & (days <= 280)
)

north_limit[north_solar_constraint] *= 0.75

grid = pd.DataFrame({
    "timestamp": timestamps,
    "north_export_limit_mw": north_limit,
    "central_export_limit_mw": central_limit,
})


# ============================================================
# 8. BESS DISPATCH — CLEAN TRUTH
# ============================================================

bess_config = {
    "North": {"power_mw": 50, "energy_mwh": 200},
    "Central": {"power_mw": 50, "energy_mwh": 200},
}

# Regional potential generation.
potential_by_asset = potential_generation.merge(
    assets[["asset_id", "region", "technology"]],
    on="asset_id",
    how="left"
)

regional_potential = (
    potential_by_asset.groupby(
        ["timestamp", "region"],
        as_index=False
    )["potential_generation_mwh"].sum()
)

potential_pivot = regional_potential.pivot(
    index="timestamp",
    columns="region",
    values="potential_generation_mwh"
).fillna(0)

north_potential = potential_pivot["North"].to_numpy()
central_potential = potential_pivot["Central"].to_numpy()

# Regional demand allocation.
# North is modeled as the generation-heavy / lower-demand region.
north_demand = demand * 0.45
central_demand = demand * 0.55

bess_rows = []

soc_state = {
    "North": 170.0,
    "Central": 150.0,
}

for i, ts in enumerate(timestamps):

    for region in ["North", "Central"]:

        cfg = bess_config[region]

        power = cfg["power_mw"]
        energy = cfg["energy_mwh"]

        potential_region = (
            north_potential[i]
            if region == "North"
            else central_potential[i]
        )

        demand_region = (
            north_demand[i]
            if region == "North"
            else central_demand[i]
        )

        export_limit = (
            north_limit[i]
            if region == "North"
            else central_limit[i]
        )

        # Estimate immediate surplus before BESS.
        pre_bess_surplus = max(
            potential_region
            - demand_region
            - export_limit,
            0
        )

        # Charge mainly during surplus / midday.
        charge_request = 0

        if 9 <= ts.hour <= 15 and pre_bess_surplus > 0:
            charge_request = min(
                power,
                pre_bess_surplus
            )

        available_room = max(
            energy - soc_state[region],
            0
        )

        charge = min(
            charge_request,
            available_room / 0.94
        )

        soc_state[region] += charge * 0.94

        # Discharge during evening when demand is high.
        discharge_request = 0

        if 17 <= ts.hour <= 22:
            discharge_request = min(
                power * 0.75,
                max(demand_region - potential_region, 0)
            )

        discharge = min(
            discharge_request,
            soc_state[region] * 0.92
        )

        soc_state[region] -= discharge / 0.92

        soc_state[region] = np.clip(
            soc_state[region],
            0,
            energy
        )

        bess_rows.append({
            "timestamp": ts,
            "region": region,
            "battery_power_capacity_mw": power,
            "battery_energy_capacity_mwh": energy,
            "soc_mwh": soc_state[region],
            "charge_mwh": charge,
            "discharge_mwh": discharge,
        })

bess_clean = pd.DataFrame(bess_rows)


# ============================================================
# 9. SYSTEM DISPATCH LOGIC
# ============================================================
# This is the core business/physical logic.
#
# Renewable energy can be absorbed by:
#   1. Local demand
#   2. Grid export
#   3. BESS charging
#
# Anything beyond those constraints is curtailed.

bess_hourly = (
    bess_clean.groupby("timestamp", as_index=False)
    .agg(
        north_charge_mwh=("charge_mwh", lambda x: x.iloc[0]),
        central_charge_mwh=("charge_mwh", lambda x: x.iloc[1]),
        north_soc_mwh=("soc_mwh", lambda x: x.iloc[0]),
        central_soc_mwh=("soc_mwh", lambda x: x.iloc[1]),
    )
)

north_charge = bess_hourly["north_charge_mwh"].to_numpy()
central_charge = bess_hourly["central_charge_mwh"].to_numpy()

# Renewable absorption capacity.
north_absorption = (
    north_demand
    + north_limit
    + north_charge
)

central_absorption = (
    central_demand
    + central_limit
    + central_charge
)

north_actual = np.minimum(
    north_potential,
    north_absorption
)

central_actual = np.minimum(
    central_potential,
    central_absorption
)

north_curtailment = np.maximum(
    north_potential - north_actual,
    0
)

central_curtailment = np.maximum(
    central_potential - central_actual,
    0
)


# ============================================================
# 10. ALLOCATE REGIONAL ACTUAL GENERATION BACK TO ASSETS
# ============================================================

potential_generation["region"] = potential_generation["asset_id"].map(
    assets.set_index("asset_id")["region"]
)

potential_generation["actual_generation_mwh"] = 0.0
potential_generation["curtailment_mwh"] = 0.0

for region in ["North", "Central"]:

    region_mask = potential_generation["region"] == region

    region_potential = (
        potential_generation.loc[region_mask]
        .groupby("timestamp")["potential_generation_mwh"]
        .transform("sum")
    )

    region_curtailment = pd.Series(
        north_curtailment
        if region == "North"
        else central_curtailment,
        index=timestamps
    )

    current_rows = potential_generation.loc[region_mask]

    shares = np.divide(
        current_rows["potential_generation_mwh"].to_numpy(),
        region_potential.to_numpy(),
        out=np.zeros(len(current_rows)),
        where=region_potential.to_numpy() > 0
    )

    allocated_curtailment = (
        shares
        * current_rows["timestamp"].map(region_curtailment).to_numpy()
    )

    actual = (
        current_rows["potential_generation_mwh"].to_numpy()
        - allocated_curtailment
    )

    potential_generation.loc[
        region_mask,
        "curtailment_mwh"
    ] = allocated_curtailment

    potential_generation.loc[
        region_mask,
        "actual_generation_mwh"
    ] = actual


# ============================================================
# 11. CURTAILMENT CAUSE CLASSIFICATION
# ============================================================
# Cause is based on the binding constraint in the clean truth.

def classify_reason(ts, region):
    i = timestamps.get_loc(ts)

    potential_region = (
        north_potential[i]
        if region == "North"
        else central_potential[i]
    )

    demand_region = (
        north_demand[i]
        if region == "North"
        else central_demand[i]
    )

    export = (
        north_limit[i]
        if region == "North"
        else central_limit[i]
    )

    charge = (
        north_charge[i]
        if region == "North"
        else central_charge[i]
    )

    if potential_region <= demand_region + export + charge + 1e-9:
        return "none"

    # When export capacity is strongly constrained, classify as grid constraint.
    normal_export = 80 if region == "North" else 220

    if export < normal_export * 0.93:
        return "grid_constraint"

    # High renewable / low demand and battery unable to absorb all surplus.
    if (
        10 <= ts.hour <= 15
        and potential_region > demand_region
        and charge >= bess_config[region]["power_mw"] * 0.95
    ):
        return "storage_constraint"

    if potential_region > demand_region + export:
        return "low_demand_surplus"

    return "system_balancing"


potential_generation["curtailment_reason"] = "none"

for region in ["North", "Central"]:

    mask = (
        potential_generation["region"] == region
    )

    potential_generation.loc[
        mask,
        "curtailment_reason"
    ] = [
        classify_reason(ts, region)
        for ts in potential_generation.loc[mask, "timestamp"]
    ]


# ============================================================
# 12. EMS OPERATIONS — CLEAN TRUTH
# ============================================================

hourly_generation = (
    potential_generation.groupby("timestamp", as_index=False)
    .agg(
        potential_renewable_mwh=(
            "potential_generation_mwh",
            "sum"
        ),
        actual_renewable_mwh=(
            "actual_generation_mwh",
            "sum"
        ),
        curtailment_mwh=(
            "curtailment_mwh",
            "sum"
        ),
    )
)

ems_clean = hourly_generation.copy()

ems_clean["total_demand_mwh"] = demand

ems_clean["potential_surplus_mwh"] = np.maximum(
    ems_clean["potential_renewable_mwh"]
    - ems_clean["total_demand_mwh"],
    0
)

ems_clean["actual_surplus_mwh"] = np.maximum(
    ems_clean["actual_renewable_mwh"]
    - ems_clean["total_demand_mwh"],
    0
)

ems_clean["renewable_share_pct"] = (
    ems_clean["actual_renewable_mwh"]
    / ems_clean["total_demand_mwh"]
    * 100
)

ems_clean["net_load_mwh"] = (
    ems_clean["total_demand_mwh"]
    - ems_clean["actual_renewable_mwh"]
)

ems_clean["north_export_limit_mw"] = north_limit
ems_clean["central_export_limit_mw"] = central_limit

ems_clean["north_potential_mwh"] = north_potential
ems_clean["central_potential_mwh"] = central_potential

ems_clean["north_curtailment_mwh"] = north_curtailment
ems_clean["central_curtailment_mwh"] = central_curtailment

ems_clean["system_stress_flag"] = (
    (ems_clean["curtailment_mwh"] > 50)
    | (ems_clean["potential_surplus_mwh"] > 100)
).astype(int)


# ============================================================
# 13. MARKET PRICE
# ============================================================

# Price declines during periods of high renewable surplus.
price = (
    70
    + 12 * np.sin(2 * np.pi * (hours - 7) / 24)
    - 0.06 * ems_clean["potential_surplus_mwh"].to_numpy()
    + rng.normal(0, 5, n_hours)
)

price = np.clip(price, -30, 180)

negative_period = (
    (ems_clean["potential_surplus_mwh"] > 200)
    & (rng.random(n_hours) < 0.35)
)

price[negative_period] = rng.uniform(
    -15,
    -1,
    negative_period.sum()
)

market_clean = pd.DataFrame({
    "timestamp": timestamps,
    "market_price_usd_per_mwh": np.round(price, 2),
})


# ============================================================
# 14. DISPATCH / CURTAILMENT EVENT LOG — CLEAN TRUTH
# ============================================================

event_rows = []
event_id = 1

# Convert hourly curtailment into contiguous events.
for region, values in [
    ("North", north_curtailment),
    ("Central", central_curtailment),
]:

    active = values > 0.01

    start_idx = None

    for i in range(n_hours + 1):

        is_active = (
            i < n_hours
            and active[i]
        )

        if is_active and start_idx is None:
            start_idx = i

        if not is_active and start_idx is not None:

            end_idx = i - 1

            energy = values[start_idx:end_idx + 1].sum()

            if energy > 1:

                peak = values[start_idx:end_idx + 1].max()

                if peak >= 100:
                    severity = "High"
                elif peak >= 50:
                    severity = "Medium"
                else:
                    severity = "Low"

                reasons = [
                    classify_reason(timestamps[j], region)
                    for j in range(start_idx, end_idx + 1)
                ]

                # Dominant reason.
                reason = pd.Series(reasons).value_counts().index[0]

                event_rows.append({
                    "event_id": f"CE-{event_id:05d}",
                    "region": region,
                    "start_time": timestamps[start_idx],
                    "end_time": timestamps[end_idx],
                    "duration_hours": end_idx - start_idx + 1,
                    "severity": severity,
                    "reason": reason,
                    "curtailed_energy_mwh": energy,
                    "operator_action": "Dispatch down renewable output",
                })

                event_id += 1

            start_idx = None

dispatch_clean = pd.DataFrame(event_rows)


# ============================================================
# 15. CLEAN TRUTH HOURLY RECONCILIATION
# ============================================================

clean_truth = ems_clean[
    [
        "timestamp",
        "total_demand_mwh",
        "potential_renewable_mwh",
        "actual_renewable_mwh",
        "curtailment_mwh",
        "potential_surplus_mwh",
        "actual_surplus_mwh",
        "renewable_share_pct",
        "north_export_limit_mw",
        "central_export_limit_mw",
        "north_curtailment_mwh",
        "central_curtailment_mwh",
    ]
].copy()

clean_truth["reconciliation_check_mwh"] = (
    clean_truth["potential_renewable_mwh"]
    - clean_truth["actual_renewable_mwh"]
    - clean_truth["curtailment_mwh"]
)


# ============================================================
# 16. RAW EXTRACT BUILDERS
# ============================================================

scada_clean = potential_generation[
    [
        "timestamp",
        "asset_id",
        "capacity_mw",
        "availability_pct",
        "capacity_factor",
        "potential_generation_mwh",
        "actual_generation_mwh",
        "curtailment_mwh",
    ]
].copy()

scada_clean["source_system"] = "SCADA"
scada_clean["reading_status"] = "VALID"

ems_raw = ems_clean.copy()
ems_raw["source_system"] = "EMS"
ems_raw["demand_unit"] = "MWh"
ems_raw["record_status"] = "VALID"

bess_raw = bess_clean.copy()
bess_raw["source_system"] = "BESS_CONTROLLER"
bess_raw["record_status"] = "VALID"

weather_raw = weather.copy()
weather_raw["source_system"] = "WEATHER_STATION"
weather_raw["record_status"] = "VALID"

market_raw = market_clean.copy()
market_raw["source_system"] = "MARKET_FEED"
market_raw["record_status"] = "VALID"

dispatch_raw = dispatch_clean.copy()
dispatch_raw["source_system"] = "DISPATCH_LOG"
dispatch_raw["record_status"] = "VALID"

asset_raw = assets.copy()
asset_raw["source_system"] = "ASSET_REGISTRY"


# ============================================================
# 17. RAW DATA QUALITY ISSUE INJECTION
# ============================================================

issue_log = []


def record_issue(table, issue_type, column, count, description):
    issue_log.append({
        "table": table,
        "issue_type": issue_type,
        "column": column,
        "affected_records": int(count),
        "description": description,
    })


def inject_duplicates(df, table, fraction=0.002):
    if len(df) < 100:
        return df

    count = max(2, int(len(df) * fraction))
    dup = df.sample(count, random_state=SEED)

    record_issue(
        table,
        "duplicate_rows",
        "multiple_columns",
        count,
        "Exact duplicate records inserted to simulate repeated source extraction."
    )

    return pd.concat([df, dup], ignore_index=True)


def inject_missing(df, table, column, fraction=0.002):
    count = max(2, int(len(df) * fraction))
    count = min(count, len(df))

    idx = rng.choice(df.index, count, replace=False)
    df.loc[idx, column] = np.nan

    record_issue(
        table,
        "missing_values",
        column,
        count,
        "Random operational readings removed from raw extract."
    )

    return df


def inject_category_noise(df, table, column, fraction=0.01):
    if column not in df.columns:
        return df

    valid_idx = df.index[df[column].notna()]

    if len(valid_idx) == 0:
        return df

    count = min(
        max(2, int(len(df) * fraction)),
        len(valid_idx)
    )

    idx = rng.choice(valid_idx, count, replace=False)

    for i in idx:
        value = str(df.loc[i, column])

        df.loc[i, column] = rng.choice([
            value.upper(),
            value.lower(),
            f" {value}",
            f"{value} ",
        ])

    record_issue(
        table,
        "inconsistent_categories",
        column,
        count,
        "Capitalization and whitespace variations inserted."
    )

    return df


def inject_timestamp_noise(df, table, fraction=0.004):
    if "timestamp" not in df.columns:
        return df

    count = max(2, int(len(df) * fraction))
    count = min(count, len(df))

    idx = rng.choice(df.index, count, replace=False)

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y/%m/%d %H:%M",
        "%m-%d-%Y %H:%M",
    ]

    for i in idx:
        ts = pd.to_datetime(df.loc[i, "timestamp"])
        df.loc[i, "timestamp"] = ts.strftime(
            rng.choice(formats)
        )

    record_issue(
        table,
        "timestamp_format",
        "timestamp",
        count,
        "Multiple timestamp formats inserted."
    )

    return df


def inject_numeric_as_text(df, table, column, fraction=0.003):
    if column not in df.columns:
        return df

    valid_idx = df.index[df[column].notna()]

    if len(valid_idx) == 0:
        return df

    count = min(
        max(2, int(len(df) * fraction)),
        len(valid_idx)
    )

    idx = rng.choice(valid_idx, count, replace=False)

    # Intentionally create a mixed-type raw column without triggering
    # pandas incompatible-dtype warnings.
    df[column] = df[column].astype("object")

    for i in idx:
        value = df.loc[i, column]
        df.loc[i, column] = str(value)

    record_issue(
        table,
        "numeric_as_text",
        column,
        count,
        "Numeric values stored as strings in source extract."
    )

    return df


# ------------------------------------------------------------
# SCADA issues
# ------------------------------------------------------------

scada_raw = inject_duplicates(
    scada_clean.copy(),
    "scada_generation_raw"
)

scada_raw = inject_missing(
    scada_raw,
    "scada_generation_raw",
    "actual_generation_mwh",
    0.003
)

scada_raw = inject_missing(
    scada_raw,
    "scada_generation_raw",
    "availability_pct",
    0.002
)

scada_raw = inject_timestamp_noise(
    scada_raw,
    "scada_generation_raw"
)

scada_raw = inject_numeric_as_text(
    scada_raw,
    "scada_generation_raw",
    "actual_generation_mwh"
)

# A few impossible SCADA readings.
outlier_idx = rng.choice(
    scada_raw.index,
    6,
    replace=False
)

scada_raw.loc[
    outlier_idx[:3],
    "actual_generation_mwh"
] = -5

scada_raw.loc[
    outlier_idx[3:],
    "actual_generation_mwh"
] = 999

record_issue(
    "scada_generation_raw",
    "physical_outlier",
    "actual_generation_mwh",
    6,
    "Impossible negative or above-capacity generation readings inserted."
)


# ------------------------------------------------------------
# EMS issues
# ------------------------------------------------------------

ems_raw = inject_duplicates(
    ems_raw,
    "ems_operations_raw"
)

ems_raw = inject_missing(
    ems_raw,
    "ems_operations_raw",
    "total_demand_mwh",
    0.002
)

ems_raw = inject_timestamp_noise(
    ems_raw,
    "ems_operations_raw"
)

ems_raw = inject_numeric_as_text(
    ems_raw,
    "ems_operations_raw",
    "total_demand_mwh"
)

# Unit-label inconsistency.
unit_idx = rng.choice(
    ems_raw.index,
    max(4, int(len(ems_raw) * 0.001)),
    replace=False
)

ems_raw.loc[unit_idx, "demand_unit"] = "MW"

record_issue(
    "ems_operations_raw",
    "unit_inconsistency",
    "demand_unit",
    len(unit_idx),
    "A small number of records use MW while the operational field is hourly MWh."
)


# ------------------------------------------------------------
# BESS issues
# ------------------------------------------------------------

bess_raw = inject_duplicates(
    bess_raw,
    "bess_operations_raw"
)

bess_raw = inject_missing(
    bess_raw,
    "bess_operations_raw",
    "soc_mwh",
    0.003
)

bess_raw = inject_timestamp_noise(
    bess_raw,
    "bess_operations_raw"
)

bess_raw = inject_category_noise(
    bess_raw,
    "bess_operations_raw",
    "region"
)

# Physically impossible SOC values.
bess_outliers = rng.choice(
    bess_raw.index,
    8,
    replace=False
)

bess_raw.loc[
    bess_outliers[:4],
    "soc_mwh"
] = -10

bess_raw.loc[
    bess_outliers[4:],
    "soc_mwh"
] = 999

record_issue(
    "bess_operations_raw",
    "physical_outlier",
    "soc_mwh",
    8,
    "SOC values outside battery energy capacity inserted."
)


# ------------------------------------------------------------
# WEATHER issues
# ------------------------------------------------------------

weather_raw = inject_duplicates(
    weather_raw,
    "weather_station_raw"
)

weather_raw = inject_missing(
    weather_raw,
    "weather_station_raw",
    "wind_speed_mps",
    0.004
)

weather_raw = inject_timestamp_noise(
    weather_raw,
    "weather_station_raw"
)

weather_outliers = rng.choice(
    weather_raw.index,
    6,
    replace=False
)

weather_raw.loc[
    weather_outliers[:3],
    "wind_speed_mps"
] = -2

weather_raw.loc[
    weather_outliers[3:],
    "wind_speed_mps"
] = 60

record_issue(
    "weather_station_raw",
    "physical_outlier",
    "wind_speed_mps",
    6,
    "Negative and implausibly high wind-speed readings inserted."
)


# ------------------------------------------------------------
# MARKET issues
# ------------------------------------------------------------

market_raw = inject_duplicates(
    market_raw,
    "market_price_raw"
)

market_raw = inject_missing(
    market_raw,
    "market_price_raw",
    "market_price_usd_per_mwh",
    0.002
)

market_raw = inject_timestamp_noise(
    market_raw,
    "market_price_raw"
)

market_raw = inject_numeric_as_text(
    market_raw,
    "market_price_raw",
    "market_price_usd_per_mwh"
)


# ------------------------------------------------------------
# DISPATCH LOG issues
# ------------------------------------------------------------

def inject_dispatch_timestamp_noise(df, table, fraction=0.01):
    if df.empty:
        return df

    for column in ["start_time", "end_time"]:
        if column not in df.columns:
            continue

        count = min(max(1, int(len(df) * fraction)), len(df))
        idx = rng.choice(df.index, count, replace=False)

        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%Y/%m/%d %H:%M",
            "%m-%d-%Y %H:%M",
        ]

        df[column] = df[column].astype("object")

        for i in idx:
            ts = pd.to_datetime(df.loc[i, column])
            df.loc[i, column] = ts.strftime(rng.choice(formats))

        record_issue(
            table,
            "timestamp_format",
            column,
            count,
            "Multiple timestamp formats inserted into dispatch event timestamps."
        )

    return df


if len(dispatch_raw) > 5:

    dispatch_raw = inject_duplicates(
        dispatch_raw,
        "dispatch_curtailment_log_raw",
        fraction=0.01
    )

    dispatch_raw = inject_category_noise(
        dispatch_raw,
        "dispatch_curtailment_log_raw",
        "reason",
        fraction=0.02
    )

    dispatch_raw = inject_missing(
        dispatch_raw,
        "dispatch_curtailment_log_raw",
        "reason",
        fraction=0.015
    )

    dispatch_raw = inject_dispatch_timestamp_noise(
        dispatch_raw,
        "dispatch_curtailment_log_raw",
        fraction=0.01
    )


# ------------------------------------------------------------
# ASSET MASTER issues
# ------------------------------------------------------------

asset_raw = inject_category_noise(
    asset_raw,
    "asset_registry_raw",
    "region",
    fraction=0.15
)

asset_raw = inject_category_noise(
    asset_raw,
    "asset_registry_raw",
    "technology",
    fraction=0.15
)


# ============================================================
# 18. WRITE RAW TABLES
# ============================================================

raw_tables = {
    "asset_registry_raw.csv": asset_raw,
    "scada_generation_raw.csv": scada_raw,
    "ems_operations_raw.csv": ems_raw,
    "bess_operations_raw.csv": bess_raw,
    "weather_station_raw.csv": weather_raw,
    "market_price_raw.csv": market_raw,
    "dispatch_curtailment_log_raw.csv": dispatch_raw,
}

for filename, df in raw_tables.items():
    df.to_csv(RAW_DIR / filename, index=False)


# ============================================================
# 19. EXPECTED KPI REFERENCE
# ============================================================

total_potential = clean_truth["potential_renewable_mwh"].sum()
total_actual = clean_truth["actual_renewable_mwh"].sum()
total_curtailment = clean_truth["curtailment_mwh"].sum()

curtailment_rate = (
    total_curtailment
    / total_potential
    * 100
)

total_potential_surplus = (
    clean_truth["potential_surplus_mwh"].sum()
)

total_actual_surplus = (
    clean_truth["actual_surplus_mwh"].sum()
)

peak_curtailment = (
    clean_truth["curtailment_mwh"].max()
)

hours_curtailed = (
    clean_truth["curtailment_mwh"] > 0.01
).sum()

high_curtailment_hours = (
    clean_truth["curtailment_mwh"] > 100
).sum()

expected_kpis = pd.DataFrame({
    "metric": [
        "total_potential_renewable_mwh",
        "total_actual_renewable_mwh",
        "total_curtailment_mwh",
        "curtailment_rate_pct",
        "total_potential_surplus_mwh",
        "total_actual_surplus_mwh",
        "peak_hourly_curtailment_mwh",
        "hours_with_curtailment",
        "hours_with_curtailment_gt_100_mwh",
    ],
    "value": [
        total_potential,
        total_actual,
        total_curtailment,
        curtailment_rate,
        total_potential_surplus,
        total_actual_surplus,
        peak_curtailment,
        hours_curtailed,
        high_curtailment_hours,
    ]
})

expected_kpis["value"] = expected_kpis["value"].round(3)

expected_kpis.to_csv(
    REF_DIR / "expected_kpis.csv",
    index=False
)


# ============================================================
# 20. DATA QUALITY ISSUE LOG
# ============================================================

issue_log_df = pd.DataFrame(issue_log)

issue_log_df.to_csv(
    REF_DIR / "data_quality_issue_log.csv",
    index=False
)


# ============================================================
# 21. CLEAN TRUTH
# ============================================================

clean_truth.to_csv(
    REF_DIR / "clean_truth_hourly.csv",
    index=False
)


# ============================================================
# 22. METADATA / README
# ============================================================

metadata = f"""
GREEN GRID ENERGY — SYNTHETIC DATASET V2.1

Period:
{START} to {END}

Resolution:
Hourly

Assets:
{len(assets)}

Regions:
North, Central

Technologies:
Solar PV, Wind

RAW SYSTEMS:
1. asset_registry_raw.csv
2. scada_generation_raw.csv
3. ems_operations_raw.csv
4. bess_operations_raw.csv
5. weather_station_raw.csv
6. market_price_raw.csv
7. dispatch_curtailment_log_raw.csv

CORE BUSINESS EQUATIONS:

Curtailment
    Potential generation - Actual generation

Potential surplus
    max(Potential renewable generation - Demand, 0)

Actual surplus
    max(Actual renewable generation - Demand, 0)

Curtailment rate
    Total curtailment / Total potential generation

SYSTEM ABSORPTION:

Renewable energy can be absorbed through:
    - local demand
    - grid export
    - BESS charging

If potential generation exceeds the available absorption capacity,
the difference becomes curtailment.

IMPORTANT:
The raw tables contain intentional data-quality problems.
The reference folder contains the clean synthetic truth and expected KPIs
for validation. Do not use reference files as the final analysis dataset.

BUSINESS SIGNAL:
The North region is deliberately designed to experience stronger
curtailment pressure because of:
    - high renewable concentration
    - lower export capacity
    - midday solar generation
    - low-demand periods
    - finite BESS capacity

The dataset is intended for a Data Analyst portfolio project involving:
    Data profiling
    Data cleaning
    Data validation
    Data reconciliation
    Exploratory analysis
    Curtailment analysis
    Surplus analysis
    Root-cause analysis
    Economic impact analysis
    Strategic recommendations
"""

(META_DIR / "README_generator.txt").write_text(
    metadata,
    encoding="utf-8"
)


# ============================================================
# 23. FINAL CONSOLE SUMMARY
# ============================================================

north_curt = clean_truth["north_curtailment_mwh"].sum()
central_curt = clean_truth["central_curtailment_mwh"].sum()

print("\n" + "=" * 72)
print("GREEN GRID ENERGY — SYNTHETIC DATASET V2.1")
print("=" * 72)
print(f"Period                  : {START} → {END}")
print(f"Hourly observations     : {n_hours:,}")
print(f"Renewable assets        : {len(assets)}")
print(f"Potential generation    : {total_potential:,.0f} MWh")
print(f"Actual generation       : {total_actual:,.0f} MWh")
print(f"Curtailed energy        : {total_curtailment:,.0f} MWh")
print(f"Curtailment rate        : {curtailment_rate:.2f}%")
print(f"Potential surplus       : {total_potential_surplus:,.0f} MWh")
print(f"Actual surplus          : {total_actual_surplus:,.0f} MWh")
print(f"North curtailment       : {north_curt:,.0f} MWh")
print(f"Central curtailment     : {central_curt:,.0f} MWh")
north_curtailment_share = (
    north_curt / total_curtailment * 100
    if total_curtailment > 0
    else 0.0
)
print(f"North curtailment share : {north_curtailment_share:.1f}%")
print(f"Curtailed hours         : {hours_curtailed:,}")
print(f"High-curtailment hours  : {high_curtailment_hours:,}")
print("-" * 72)
print(f"RAW DATA                : {RAW_DIR.resolve()}")
print(f"REFERENCE               : {REF_DIR.resolve()}")
print(f"METADATA                : {META_DIR.resolve()}")
print("=" * 72)
