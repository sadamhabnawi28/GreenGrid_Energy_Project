from pathlib import Path

script = r'''"""
GreenGrid Energy — Synthetic Renewable Curtailment & Energy Surplus Dataset Generator

Purpose
-------
Generate realistic, messy operational datasets for a Data Analyst portfolio project
about Renewable Curtailment & Energy Surplus Analysis.

Business scenario
-----------------
GreenGrid Energy operates solar and wind assets connected to a constrained grid.
The Energy Management team wants to understand:
1. How much renewable energy is curtailed?
2. When and where does curtailment happen?
3. Is it associated with low demand, grid/export constraints, or limited storage?
4. What is the estimated economic value of curtailed energy?
5. Which assets/regions create the largest mitigation opportunities?

Important
---------
This is SYNTHETIC data. It is intentionally designed so that the business problem
is visible and material, while the raw files contain realistic data-quality issues.

Generated files
---------------
raw_data/
    asset_master_raw.csv
    renewable_generation_raw.csv
    system_operations_raw.csv
    battery_operations_raw.csv
    weather_raw.csv
    market_prices_raw.csv
    curtailment_events_raw.csv

clean_reference/
    expected_kpis.csv

Design targets
--------------
- 2 regions: North and Central
- 6 renewable assets: 4 solar + 2 wind
- 1 year of hourly observations
- Material curtailment, concentrated in the North region
- Strong midday solar surplus pattern
- Higher curtailment on weekends / low-demand periods
- Grid/export constraints contribute to curtailment
- Battery helps absorb some surplus but becomes constrained when SOC is high
- Raw data contains duplicates, missing values, inconsistent text, unit problems,
  malformed values, and a few operational outliers
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

OUT_DIR = Path("greengrid_renewable_curtailment_dataset")
RAW_DIR = OUT_DIR / "raw_data"
REF_DIR = OUT_DIR / "clean_reference"

rng = np.random.default_rng(SEED)

RAW_DIR.mkdir(parents=True, exist_ok=True)
REF_DIR.mkdir(parents=True, exist_ok=True)

timestamps = pd.date_range(START, END, freq="h")
n = len(timestamps)

print(f"Generating {n:,} hourly observations...")


# ============================================================
# 2. MASTER DATA
# ============================================================

assets = pd.DataFrame([
    {
        "asset_id": "SOL-N01",
        "asset_name": "North Solar One",
        "technology": "Solar PV",
        "region": "North",
        "capacity_mw": 180,
        "commission_date": "2023-06-01",
        "grid_node": "NORTH-A",
    },
    {
        "asset_id": "SOL-N02",
        "asset_name": "North Solar Two",
        "technology": "Solar PV",
        "region": "North",
        "capacity_mw": 140,
        "commission_date": "2024-03-15",
        "grid_node": "NORTH-A",
    },
    {
        "asset_id": "WND-N01",
        "asset_name": "North Wind One",
        "technology": "Wind",
        "region": "North",
        "capacity_mw": 220,
        "commission_date": "2022-10-01",
        "grid_node": "NORTH-B",
    },
    {
        "asset_id": "SOL-C01",
        "asset_name": "Central Solar One",
        "technology": "Solar PV",
        "region": "Central",
        "capacity_mw": 160,
        "commission_date": "2023-01-10",
        "grid_node": "CENTRAL-A",
    },
    {
        "asset_id": "SOL-C02",
        "asset_name": "Central Solar Two",
        "technology": "Solar PV",
        "region": "Central",
        "capacity_mw": 110,
        "commission_date": "2024-07-01",
        "grid_node": "CENTRAL-A",
    },
    {
        "asset_id": "WND-C01",
        "asset_name": "Central Wind One",
        "technology": "Wind",
        "region": "Central",
        "capacity_mw": 180,
        "commission_date": "2022-05-20",
        "grid_node": "CENTRAL-B",
    },
])

assets["commission_date"] = pd.to_datetime(assets["commission_date"])

# Grid and storage configuration by region.
region_config = pd.DataFrame([
    {
        "region": "North",
        "grid_export_limit_mw": 365,
        "battery_power_mw": 100,
        "battery_energy_mwh": 400,
    },
    {
        "region": "Central",
        "grid_export_limit_mw": 470,
        "battery_power_mw": 80,
        "battery_energy_mwh": 320,
    },
])


# ============================================================
# 3. WEATHER / RESOURCE SIGNAL
# ============================================================

dt = timestamps
hour = dt.hour.to_numpy()
day_of_year = dt.dayofyear.to_numpy()
weekday = dt.dayofweek.to_numpy()

# Solar daylight curve: zero at night, strong around noon.
solar_angle = (hour - 12) / 6
solar_shape = np.clip(1 - solar_angle**2, 0, None)

# Seasonal solar effect.
seasonal_solar = (
    0.88
    + 0.12 * np.cos(2 * np.pi * (day_of_year - 172) / 365)
)

# Cloud factor with persistence-like noise.
cloud_noise = np.clip(
    0.92 + rng.normal(0, 0.13, n),
    0.25,
    1.05
)

# Add cloudy episodes.
cloud_event = rng.random(n) < 0.035
cloud_factor = np.where(
    cloud_event,
    np.clip(rng.normal(0.45, 0.12, n), 0.10, 0.75),
    cloud_noise
)

irradiance_index = np.clip(
    solar_shape * seasonal_solar * cloud_factor,
    0,
    1.05
)

# Wind varies throughout the year and by hour.
wind_season = (
    0.82
    + 0.16 * np.sin(2 * np.pi * (day_of_year - 40) / 365)
)

wind_hourly = (
    0.65
    + 0.18 * np.sin(2 * np.pi * hour / 24 + 1.3)
    + rng.normal(0, 0.16, n)
)

wind_speed_ms = np.clip(
    7.5 * wind_season + 2.2 * wind_hourly,
    1.5,
    16
)

# Wind power curve approximation.
wind_cf = np.select(
    [
        wind_speed_ms < 3,
        wind_speed_ms < 12,
        wind_speed_ms < 16,
        wind_speed_ms >= 16,
    ],
    [
        0.0,
        ((wind_speed_ms - 3) / 9) ** 3 * 0.95,
        0.95,
        0.20,
    ],
)

temperature_c = (
    26
    + 4 * np.sin(2 * np.pi * (hour - 14) / 24)
    + 2 * np.sin(2 * np.pi * day_of_year / 365)
    + rng.normal(0, 1.4, n)
)

weather = pd.DataFrame({
    "timestamp": dt,
    "solar_irradiance_index": np.round(irradiance_index, 3),
    "wind_speed_mps": np.round(wind_speed_ms, 2),
    "temperature_c": np.round(temperature_c, 2),
    "cloud_cover_pct": np.round(
        np.clip(100 * (1 - cloud_factor), 0, 100), 1
    ),
})

# ============================================================
# 4. ELECTRICITY DEMAND
# ============================================================

# Base demand with morning/evening peaks.
morning_peak = 110 * np.exp(-((hour - 8) / 2.6) ** 2)
evening_peak = 180 * np.exp(-((hour - 19) / 3.0) ** 2)
midday_load = 55 * np.exp(-((hour - 13) / 4.5) ** 2)

weekday_factor = np.where(weekday < 5, 1.0, 0.82)

# Seasonal demand is slightly higher in hot months due to cooling load.
season_factor = (
    1
    + 0.08 * np.sin(2 * np.pi * (day_of_year - 25) / 365)
)

total_demand_mw = (
    (
        310
        + morning_peak
        + evening_peak
        + midday_load
    )
    * weekday_factor
    * season_factor
    + rng.normal(0, 18, n)
)

# Low-demand weekend/off-peak events make surplus more visible.
low_demand_event = (
    ((weekday >= 5) & (hour >= 10) & (hour <= 15))
    & (rng.random(n) < 0.28)
)
total_demand_mw = np.where(
    low_demand_event,
    total_demand_mw * rng.uniform(0.82, 0.93, n),
    total_demand_mw
)

total_demand_mw = np.clip(total_demand_mw, 180, None)


# ============================================================
# 5. RENEWABLE POTENTIAL GENERATION
# ============================================================

generation_rows = []

for _, asset in assets.iterrows():
    if asset["technology"] == "Solar PV":
        cf = irradiance_index * rng.uniform(0.94, 1.02, n)
        cf *= rng.normal(0.985, 0.015, n)
    else:
        cf = wind_cf * rng.uniform(0.94, 1.02, n)
        cf *= rng.normal(0.985, 0.02, n)

    # Small availability losses.
    availability = np.clip(
        rng.normal(0.985, 0.012, n),
        0.90,
        1.0
    )

    # Planned maintenance windows.
    maintenance = np.zeros(n, dtype=bool)

    # A few maintenance blocks per asset.
    for _ in range(3):
        start_idx = rng.integers(0, n - 72)
        duration = int(rng.integers(8, 36))
        maintenance[start_idx:start_idx + duration] = True

    availability = np.where(
        maintenance,
        availability * rng.uniform(0.05, 0.35),
        availability
    )

    potential_mw = np.clip(
        asset["capacity_mw"] * cf * availability,
        0,
        asset["capacity_mw"]
    )

    for i in range(n):
        generation_rows.append({
            "timestamp": timestamps[i],
            "asset_id": asset["asset_id"],
            "asset_name": asset["asset_name"],
            "technology": asset["technology"],
            "region": asset["region"],
            "capacity_mw": asset["capacity_mw"],
            "availability_pct": round(availability[i] * 100, 2),
            "potential_generation_mwh": round(potential_mw[i], 3),
        })

generation = pd.DataFrame(generation_rows)


# ============================================================
# 6. SYSTEM-LEVEL RENEWABLE POTENTIAL
# ============================================================

hourly_potential = (
    generation.groupby(["timestamp", "region"], as_index=False)
    ["potential_generation_mwh"]
    .sum()
)

potential_by_region = hourly_potential.pivot(
    index="timestamp",
    columns="region",
    values="potential_generation_mwh"
).fillna(0)

north_potential = potential_by_region["North"].to_numpy()
central_potential = potential_by_region["Central"].to_numpy()

total_potential = north_potential + central_potential


# ============================================================
# 7. GRID CONSTRAINT / EXPORT CAPACITY
# ============================================================

# Grid availability is normally high, but there are realistic constraint events.
north_grid_limit = np.full(n, 365.0)
central_grid_limit = np.full(n, 470.0)

# Planned/forced transmission constraints.
for region, limit_array in [
    ("North", north_grid_limit),
    ("Central", central_grid_limit),
]:
    for _ in range(18):
        start_idx = rng.integers(0, n - 12)
        duration = int(rng.integers(2, 13))

        reduction = rng.choice(
            [0.70, 0.80, 0.88],
            p=[0.25, 0.45, 0.30]
        )

        limit_array[start_idx:start_idx + duration] *= reduction

# Additional seasonal bottleneck in North during high solar hours.
north_midday = (
    (hour >= 10)
    & (hour <= 15)
    & (day_of_year >= 90)
    & (day_of_year <= 280)
)
north_grid_limit = np.where(
    north_midday,
    north_grid_limit * 0.94,
    north_grid_limit
)

grid = pd.DataFrame({
    "timestamp": timestamps,
    "north_export_limit_mw": np.round(north_grid_limit, 2),
    "central_export_limit_mw": np.round(central_grid_limit, 2),
})


# ============================================================
# 8. BATTERY OPERATIONS
# ============================================================

battery_rows = []

for region in ["North", "Central"]:
    cfg = region_config.loc[
        region_config["region"] == region
    ].iloc[0]

    power = cfg["battery_power_mw"]
    energy = cfg["battery_energy_mwh"]

    soc = np.empty(n)
    charge = np.zeros(n)
    discharge = np.zeros(n)

    soc_value = energy * 0.45

    for i in range(n):
        # Battery tends to charge during midday surplus periods.
        is_midday = 10 <= hour[i] <= 15
        is_evening = 17 <= hour[i] <= 22

        if is_midday and rng.random() < 0.60:
            charge_power = rng.uniform(0, power * 0.95)
            available_room = energy - soc_value
            charge[i] = min(charge_power, available_room)
            soc_value += charge[i] * 0.94

        elif is_evening and rng.random() < 0.45:
            discharge_power = rng.uniform(0, power * 0.80)
            discharge_power = min(discharge_power, soc_value)
            discharge[i] = discharge_power
            soc_value -= discharge[i] / 0.92

        # Natural operational noise.
        soc_value = np.clip(
            soc_value + rng.normal(0, 0.4),
            0,
            energy
        )

        soc[i] = soc_value

    battery_rows.extend([
        {
            "timestamp": timestamps[i],
            "region": region,
            "battery_power_capacity_mw": power,
            "battery_energy_capacity_mwh": energy,
            "soc_mwh": round(soc[i], 3),
            "charge_mwh": round(charge[i], 3),
            "discharge_mwh": round(discharge[i], 3),
        }
        for i in range(n)
    ])

battery = pd.DataFrame(battery_rows)


# ============================================================
# 9. ALLOCATE ACTUAL GENERATION AND CURTAILMENT
# ============================================================

system = pd.DataFrame({
    "timestamp": timestamps,
    "total_demand_mw": total_demand_mw,
    "north_potential_mwh": north_potential,
    "central_potential_mwh": central_potential,
    "total_potential_mwh": total_potential,
})

battery_summary = (
    battery.groupby(["timestamp", "region"], as_index=False)
    .agg(
        charge_mwh=("charge_mwh", "sum"),
        discharge_mwh=("discharge_mwh", "sum"),
        soc_mwh=("soc_mwh", "mean"),
        battery_energy_capacity_mwh=("battery_energy_capacity_mwh", "mean"),
    )
)

bat_pivot = battery_summary.pivot(
    index="timestamp",
    columns="region",
    values=["charge_mwh", "discharge_mwh", "soc_mwh",
            "battery_energy_capacity_mwh"]
)

north_charge = bat_pivot["charge_mwh"]["North"].to_numpy()
central_charge = bat_pivot["charge_mwh"]["Central"].to_numpy()

north_soc = bat_pivot["soc_mwh"]["North"].to_numpy()
central_soc = bat_pivot["soc_mwh"]["Central"].to_numpy()

# Available grid/export capacity.
north_export = north_grid_limit
central_export = central_grid_limit

# Demand is allocated between regions with a North-heavy load profile.
north_demand = total_demand_mw * 0.52
central_demand = total_demand_mw * 0.48

# Regional absorption capacity.
north_absorption = (
    north_demand
    + north_export
    + north_charge
)
central_absorption = (
    central_demand
    + central_export
    + central_charge
)

# Renewable actual generation is constrained by demand/export/storage.
north_actual = np.minimum(
    north_potential,
    north_absorption
)

central_actual = np.minimum(
    central_potential,
    central_absorption
)

# Force meaningful but not absurd curtailment during low-demand/high-solar periods.
north_surplus_pressure = (
    (hour >= 10)
    & (hour <= 15)
    & (north_potential > north_demand * 0.62)
)

central_surplus_pressure = (
    (hour >= 11)
    & (hour <= 14)
    & (central_potential > central_demand * 0.55)
)

north_extra_curtailment = np.where(
    north_surplus_pressure,
    np.maximum(
        north_potential - north_demand - north_charge - north_export * 0.92,
        0
    ),
    0
)

central_extra_curtailment = np.where(
    central_surplus_pressure,
    np.maximum(
        central_potential - central_demand - central_charge - central_export * 0.96,
        0
    ),
    0
)

north_actual = np.minimum(
    north_actual,
    north_potential - north_extra_curtailment
)

central_actual = np.minimum(
    central_actual,
    central_potential - central_extra_curtailment
)

north_curtailment = np.maximum(
    north_potential - north_actual,
    0
)

central_curtailment = np.maximum(
    central_potential - central_actual,
    0
)

# Allocate regional curtailment back to individual assets.
generation["potential_generation_mwh"] = generation["potential_generation_mwh"].astype(float)

generation["actual_generation_mwh"] = np.nan
generation["curtailment_mwh"] = np.nan
generation["curtailment_reason"] = "none"

for region in ["North", "Central"]:
    region_mask = generation["region"].eq(region)

    region_potential = (
        generation.loc[region_mask]
        .groupby("timestamp")["potential_generation_mwh"]
        .sum()
    )

    region_curt = (
        north_curtailment
        if region == "North"
        else central_curtailment
    )

    curt_by_time = pd.Series(
        region_curt,
        index=timestamps
    )

    for asset_id in generation.loc[region_mask, "asset_id"].unique():
        asset_mask = region_mask & generation["asset_id"].eq(asset_id)

        asset_potential = generation.loc[
            asset_mask, "potential_generation_mwh"
        ]

        timestamp_index = generation.loc[
            asset_mask, "timestamp"
        ]

        total_region_potential_for_asset = region_potential.reindex(
            timestamp_index
        ).to_numpy()

        asset_share = np.divide(
            asset_potential.to_numpy(),
            total_region_potential_for_asset,
            out=np.zeros(len(asset_potential)),
            where=total_region_potential_for_asset > 0
        )

        allocated_curt = (
            curt_by_time.reindex(timestamp_index).to_numpy()
            * asset_share
        )

        actual = np.maximum(
            asset_potential.to_numpy() - allocated_curt,
            0
        )

        generation.loc[asset_mask, "curtailment_mwh"] = allocated_curt
        generation.loc[asset_mask, "actual_generation_mwh"] = actual

        # Reason allocation.
        for idx, curt_value in zip(
            generation.index[asset_mask],
            allocated_curt
        ):
            if curt_value <= 0.001:
                generation.loc[idx, "curtailment_reason"] = "none"
            else:
                ts = generation.loc[idx, "timestamp"]
                h = ts.hour

                if (
                    region == "North"
                    and 10 <= h <= 15
                    and north_grid_limit[ts.hour if False else ts.dayofyear - 1] < 365
                ):
                    reason = "grid_constraint"
                elif 10 <= h <= 15:
                    reason = "low_demand_surplus"
                else:
                    reason = "system_constraint"

                generation.loc[idx, "curtailment_reason"] = reason


# ============================================================
# 10. SYSTEM OPERATIONS TABLE
# ============================================================

actual_by_hour = (
    generation.groupby("timestamp", as_index=False)
    .agg(
        renewable_potential_mwh=("potential_generation_mwh", "sum"),
        renewable_actual_mwh=("actual_generation_mwh", "sum"),
        curtailment_mwh=("curtailment_mwh", "sum"),
    )
)

system = system.merge(actual_by_hour, on="timestamp", how="left")

system["renewable_surplus_mwh"] = np.maximum(
    system["renewable_actual_mwh"]
    - system["total_demand_mw"],
    0
)

system["potential_surplus_mwh"] = np.maximum(
    system["renewable_potential_mwh"]
    - system["total_demand_mw"],
    0
)

system["renewable_share_pct"] = (
    system["renewable_actual_mwh"]
    / system["total_demand_mw"]
    * 100
)

system["net_load_mw"] = (
    system["total_demand_mw"]
    - system["renewable_actual_mwh"]
)

system["north_export_limit_mw"] = north_export
system["central_export_limit_mw"] = central_export

system["system_stress_flag"] = np.where(
    (
        system["potential_surplus_mwh"] > 100
    )
    | (
        system["curtailment_mwh"] > 50
    ),
    1,
    0
)


# ============================================================
# 11. MARKET PRICE
# ============================================================

# Prices tend to fall during high-renewable / low-demand periods.
base_price = (
    68
    + 16 * np.sin(2 * np.pi * (hour - 7) / 24)
    + 9 * np.sin(2 * np.pi * day_of_year / 365)
)

price = (
    base_price
    - 0.075 * system["renewable_surplus_mwh"].to_numpy()
    + rng.normal(0, 7, n)
)

price = np.clip(price, -35, 180)

market = pd.DataFrame({
    "timestamp": timestamps,
    "market_price_usd_per_mwh": np.round(price, 2),
})

# A few negative-price periods are deliberately created.
negative_price_mask = (
    (system["renewable_surplus_mwh"].to_numpy() > 180)
    & (rng.random(n) < 0.45)
)

market.loc[negative_price_mask, "market_price_usd_per_mwh"] = np.round(
    rng.uniform(-18, -1, negative_price_mask.sum()),
    2
)


# ============================================================
# 12. CURTAILMENT EVENT LOG
# ============================================================

events = []

curt_hourly = system[
    system["curtailment_mwh"] > 15
].copy()

event_id = 1

for _, row in curt_hourly.iterrows():
    ts = row["timestamp"]

    if row["curtailment_mwh"] > 100:
        severity = "High"
    elif row["curtailment_mwh"] > 50:
        severity = "Medium"
    else:
        severity = "Low"

    # Dominant cause inferred from system conditions.
    north_c = north_curtailment[ts.hour if False else ts.dayofyear - 1]
    central_c = central_curtailment[ts.hour if False else ts.dayofyear - 1]

    if (
        row["renewable_surplus_mwh"] > 120
        and ts.hour in range(10, 16)
    ):
        reason = "Low demand / renewable surplus"
    elif north_c > central_c:
        reason = "North grid constraint"
    else:
        reason = "System balancing constraint"

    events.append({
        "event_id": f"CE-{event_id:05d}",
        "event_date": ts.date(),
        "start_time": ts,
        "duration_hours": 1,
        "region": "North" if north_c > central_c else "Central",
        "severity": severity,
        "reason": reason,
        "curtailed_energy_mwh": round(row["curtailment_mwh"], 3),
        "operator_note": (
            "Dispatch-down required to maintain system balance."
        ),
    })

    event_id += 1

events = pd.DataFrame(events)


# ============================================================
# 13. INTENTIONAL RAW-DATA QUALITY ISSUES
# ============================================================

def add_raw_issues(df, table_name):
    """
    Add realistic data-quality problems without destroying the underlying
    business signal. The point is to make the analyst perform cleaning,
    validation, reconciliation and documentation.
    """
    df = df.copy()

    # 1) Duplicate rows.
    if len(df) > 100:
        dup_n = max(2, int(len(df) * 0.002))
        duplicates = df.sample(dup_n, random_state=SEED)
        df = pd.concat([df, duplicates], ignore_index=True)

    # 2) Missing numeric values.
    numeric_cols = df.select_dtypes(
        include=[np.number]
    ).columns.tolist()

    for col in numeric_cols[:4]:
        if len(df) > 100:
            missing_n = max(2, int(len(df) * 0.003))
            idx = rng.choice(df.index, size=missing_n, replace=False)
            df.loc[idx, col] = np.nan

    # 3) Whitespace / inconsistent category formatting.
    categorical_cols = df.select_dtypes(
        include=["object"]
    ).columns.tolist()

    for col in categorical_cols:
        if col in {"asset_id", "event_id"}:
            continue

        if len(df) > 100:
            idx = rng.choice(
                df.index,
                size=max(2, int(len(df) * 0.01)),
                replace=False
            )

            for i in idx:
                if pd.notna(df.loc[i, col]):
                    value = str(df.loc[i, col])
                    variant = rng.choice([
                        f" {value}",
                        f"{value} ",
                        value.upper(),
                        value.lower(),
                    ])
                    df.loc[i, col] = variant

    # 4) Timestamp formatting inconsistency.
    if "timestamp" in df.columns:
        ts_idx = rng.choice(
            df.index,
            size=max(3, int(len(df) * 0.003)),
            replace=False
        )

        for i in ts_idx:
            ts_value = pd.to_datetime(df.loc[i, "timestamp"])
            df.loc[i, "timestamp"] = ts_value.strftime(
                rng.choice([
                    "%d/%m/%Y %H:%M",
                    "%Y/%m/%d %H:%M",
                    "%m-%d-%Y %H:%M",
                ])
            )

    # 5) Numeric values represented as strings.
    for col in numeric_cols[:3]:
        if len(df) > 100:
            idx = rng.choice(
                df.index,
                size=max(2, int(len(df) * 0.004)),
                replace=False
            )
            for i in idx:
                value = df.loc[i, col]
                if pd.notna(value):
                    df.loc[i, col] = f"{value:.3f}"

    # 6) A few physically implausible outliers.
    if table_name == "weather_raw" and "wind_speed_mps" in df.columns:
        idx = rng.choice(df.index, size=4, replace=False)
        df.loc[idx, "wind_speed_mps"] = rng.choice(
            [0, 45, 60, -2],
            size=4
        )

    if table_name == "battery_operations_raw" and "soc_mwh" in df.columns:
        idx = rng.choice(df.index, size=4, replace=False)
        df.loc[idx, "soc_mwh"] = rng.choice(
            [-20, 999, 450, -5],
            size=4
        )

    return df


# ============================================================
# 14. PREPARE RAW TABLES
# ============================================================

asset_master_raw = assets.copy()

renewable_generation_raw = generation.copy()

system_operations_raw = system[
    [
        "timestamp",
        "total_demand_mw",
        "renewable_potential_mwh",
        "renewable_actual_mwh",
        "curtailment_mwh",
        "renewable_surplus_mwh",
        "potential_surplus_mwh",
        "renewable_share_pct",
        "net_load_mw",
        "north_export_limit_mw",
        "central_export_limit_mw",
        "system_stress_flag",
    ]
].copy()

battery_operations_raw = battery.copy()
weather_raw = weather.copy()
market_prices_raw = market.copy()
curtailment_events_raw = events.copy()


# Add unit labels / source-like columns to mimic operational systems.
renewable_generation_raw["source_system"] = "Plant SCADA"
system_operations_raw["source_system"] = "EMS"
battery_operations_raw["source_system"] = "BESS Controller"
weather_raw["source_system"] = "Weather Station"
market_prices_raw["source_system"] = "Market Data Feed"
curtailment_events_raw["source_system"] = "Dispatch Log"

# A deliberately inconsistent unit entry for a small number of records.
if len(system_operations_raw) > 100:
    unit_idx = rng.choice(
        system_operations_raw.index,
        size=10,
        replace=False
    )
    system_operations_raw["demand_unit"] = "MW"
    system_operations_raw.loc[
        unit_idx[:5], "demand_unit"
    ] = "kW"

# Another operational issue: some actual generation records arrive as blanks.
blank_idx = rng.choice(
    renewable_generation_raw.index,
    size=max(10, int(len(renewable_generation_raw) * 0.001)),
    replace=False
)
renewable_generation_raw.loc[
    blank_idx,
    "actual_generation_mwh"
] = np.nan


# Apply raw quality issues.
asset_master_raw = add_raw_issues(
    asset_master_raw,
    "asset_master_raw"
)

renewable_generation_raw = add_raw_issues(
    renewable_generation_raw,
    "renewable_generation_raw"
)

system_operations_raw = add_raw_issues(
    system_operations_raw,
    "system_operations_raw"
)

battery_operations_raw = add_raw_issues(
    battery_operations_raw,
    "battery_operations_raw"
)

weather_raw = add_raw_issues(
    weather_raw,
    "weather_raw"
)

market_prices_raw = add_raw_issues(
    market_prices_raw,
    "market_prices_raw"
)

curtailment_events_raw = add_raw_issues(
    curtailment_events_raw,
    "curtailment_events_raw"
)


# ============================================================
# 15. WRITE RAW DATA
# ============================================================

tables = {
    "asset_master_raw.csv": asset_master_raw,
    "renewable_generation_raw.csv": renewable_generation_raw,
    "system_operations_raw.csv": system_operations_raw,
    "battery_operations_raw.csv": battery_operations_raw,
    "weather_raw.csv": weather_raw,
    "market_prices_raw.csv": market_prices_raw,
    "curtailment_events_raw.csv": curtailment_events_raw,
}

for filename, df in tables.items():
    df.to_csv(RAW_DIR / filename, index=False)

# ============================================================
# 16. CLEAN REFERENCE / GROUND TRUTH
# ============================================================
# This is NOT intended to be used directly in the dashboard.
# It helps the analyst validate whether cleaning/calculation logic is correct.

clean_reference = pd.DataFrame({
    "metric": [
        "total_potential_generation_mwh",
        "total_actual_generation_mwh",
        "total_curtailment_mwh",
        "curtailment_rate_pct",
        "total_potential_surplus_mwh",
        "total_actual_surplus_mwh",
        "peak_hourly_curtailment_mwh",
        "hours_with_curtailment",
        "hours_with_high_curtailment_gt_100_mwh",
    ],
    "value": [
        generation["potential_generation_mwh"].sum(),
        generation["actual_generation_mwh"].sum(),
        generation["curtailment_mwh"].sum(),
        (
            generation["curtailment_mwh"].sum()
            / generation["potential_generation_mwh"].sum()
            * 100
        ),
        system["potential_surplus_mwh"].sum(),
        system["renewable_surplus_mwh"].sum(),
        system["curtailment_mwh"].max(),
        (system["curtailment_mwh"] > 0.01).sum(),
        (system["curtailment_mwh"] > 100).sum(),
    ]
})

clean_reference["value"] = clean_reference["value"].round(3)

clean_reference.to_csv(
    REF_DIR / "expected_kpis.csv",
    index=False
)


# ============================================================
# 17. BUSINESS-SIGNAL CHECK
# ============================================================

total_potential = generation["potential_generation_mwh"].sum()
total_curtailment = generation["curtailment_mwh"].sum()
curtailment_rate = total_curtailment / total_potential * 100

north_curt = generation.loc[
    generation["region"].eq("North"),
    "curtailment_mwh"
].sum()

central_curt = generation.loc[
    generation["region"].eq("Central"),
    "curtailment_mwh"
].sum()

print("\n" + "=" * 70)
print("GREEN GRID — DATA GENERATION SUMMARY")
print("=" * 70)
print(f"Period                  : {START} to {END}")
print(f"Hourly rows              : {n:,}")
print(f"Assets                   : {len(assets)}")
print(f"Raw tables               : {len(tables)}")
print(f"Potential generation     : {total_potential:,.0f} MWh")
print(f"Curtailed energy         : {total_curtailment:,.0f} MWh")
print(f"Curtailment rate         : {curtailment_rate:.2f}%")
print(f"North curtailment        : {north_curt:,.0f} MWh")
print(f"Central curtailment      : {central_curt:,.0f} MWh")
print(
    f"North share of curtail.  : "
    f"{north_curt / total_curtailment * 100:.1f}%"
)
print(
    f"Hours with curtailment   : "
    f"{(system['curtailment_mwh'] > 0.01).sum():,}"
)
print(
    f"High-curtailment hours   : "
    f"{(system['curtailment_mwh'] > 100).sum():,}"
)
print("=" * 70)
print("Raw files written to:", RAW_DIR.resolve())
print("Reference KPI written to:", REF_DIR.resolve())
print("=" * 70)
'''

path = Path("/mnt/data/generate_greengrid_dataset.py")
path.write_text(script, encoding="utf-8")

print(f"Created: {path}")
print("The script generates 7 raw operational CSV tables plus an expected KPI reference.")
