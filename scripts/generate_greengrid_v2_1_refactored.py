"""
GreenGrid Energy — Renewable Curtailment & Energy Surplus
Synthetic Operational Data Generator — Version 2.1 (Refactored)

This version is a structural refactor of V2.1. The business rules, system
relationships, intentional data-quality issues, output files, and validation
logic are kept equivalent to V2.1. The main change is organization into
classes based on functionality.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd


# ============================================================================
# 1. CONFIGURATION
# ============================================================================


@dataclass(frozen=True)
class GreenGridConfig:
    seed: int = 42
    start: str = "2025-01-01 00:00:00"
    end: str = "2025-12-31 23:00:00"
    base_dir: Path = Path("datasets/greengrid_v2_1")

    @property
    def raw_dir(self) -> Path:
        return self.base_dir / "raw_data"

    @property
    def ref_dir(self) -> Path:
        return self.base_dir / "reference"

    @property
    def meta_dir(self) -> Path:
        return self.base_dir / "metadata"


class TimeContext:
    """Creates the shared hourly time features used by all generators."""

    def __init__(self, config: GreenGridConfig):
        self.timestamps = pd.date_range(config.start, config.end, freq="h")
        self.hours = self.timestamps.hour.to_numpy()
        self.days = self.timestamps.dayofyear.to_numpy()
        self.weekdays = self.timestamps.dayofweek.to_numpy()
        self.n_hours = len(self.timestamps)


# ============================================================================
# 2. ASSET MASTER
# ============================================================================


class AssetRegistryBuilder:
    """Builds the clean asset master/reference table."""

    def build(self) -> pd.DataFrame:
        assets = pd.DataFrame(
            [
                ["SOL-N01", "North Solar One", "Solar PV", "North", "NORTH_A", 180],
                ["SOL-N02", "North Solar Two", "Solar PV", "North", "NORTH_A", 140],
                ["WND-N01", "North Wind One", "Wind", "North", "NORTH_B", 220],
                ["SOL-C01", "Central Solar One", "Solar PV", "Central", "CENTRAL_A", 160],
                ["SOL-C02", "Central Solar Two", "Solar PV", "Central", "CENTRAL_A", 110],
                ["WND-C01", "Central Wind One", "Wind", "Central", "CENTRAL_B", 180],
            ],
            columns=[
                "asset_id",
                "asset_name",
                "technology",
                "region",
                "grid_node",
                "capacity_mw",
            ],
        )

        assets["commission_date"] = pd.to_datetime(
            [
                "2023-06-01",
                "2024-03-15",
                "2022-10-01",
                "2023-01-10",
                "2024-07-01",
                "2022-05-20",
            ]
        )
        assets["asset_status"] = "Operational"
        return assets


# ============================================================================
# 3. WEATHER
# ============================================================================


class WeatherStationGenerator:
    """Generates weather/resource observations used by renewable assets."""

    def __init__(self, config: GreenGridConfig, time: TimeContext, rng):
        self.config = config
        self.time = time
        self.rng = rng

    def generate(self) -> pd.DataFrame:
        hours = self.time.hours
        days = self.time.days
        n_hours = self.time.n_hours
        timestamps = self.time.timestamps

        # Solar irradiance: daylight curve + seasonality + cloud events + noise.
        solar_day_curve = np.clip(
            1 - ((hours - 12) / 6) ** 2,
            0,
            None,
        )

        solar_season = (
            0.92
            + 0.08 * np.cos(2 * np.pi * (days - 172) / 365)
        )

        cloud_factor = np.clip(
            0.93 + self.rng.normal(0, 0.10, n_hours),
            0.30,
            1.05,
        )

        cloud_event = self.rng.random(n_hours) < 0.04
        cloud_factor = np.where(
            cloud_event,
            np.clip(self.rng.normal(0.48, 0.12, n_hours), 0.15, 0.75),
            cloud_factor,
        )

        irradiance = np.clip(
            solar_day_curve * solar_season * cloud_factor,
            0,
            1.05,
        )

        # Wind resource.
        wind_speed = (
            7.0
            + 1.3 * np.sin(2 * np.pi * (days - 40) / 365)
            + 1.0 * np.sin(2 * np.pi * hours / 24 + 1.2)
            + self.rng.normal(0, 1.3, n_hours)
        )
        wind_speed = np.clip(wind_speed, 1.0, 16.0)

        temperature = (
            27
            + 3.5 * np.sin(2 * np.pi * (hours - 14) / 24)
            + 1.8 * np.sin(2 * np.pi * days / 365)
            + self.rng.normal(0, 1.2, n_hours)
        )

        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "station_id": "WX-MASTER",
                "solar_irradiance_index": np.round(irradiance, 4),
                "wind_speed_mps": np.round(wind_speed, 3),
                "temperature_c": np.round(temperature, 2),
                "cloud_cover_pct": np.round(
                    np.clip((1 - cloud_factor) * 100, 0, 100),
                    1,
                ),
            }
        )


# ============================================================================
# 4. RENEWABLE GENERATION MODEL
# ============================================================================


class RenewableGenerationModel:
    """Creates asset availability and clean potential renewable generation."""

    def __init__(self, config: GreenGridConfig, time: TimeContext, rng):
        self.config = config
        self.time = time
        self.rng = rng

    def build_availability(self, assets: pd.DataFrame) -> Dict[str, np.ndarray]:
        availability = {}

        for _, asset in assets.iterrows():
            values = np.clip(
                self.rng.normal(0.985, 0.008, self.time.n_hours),
                0.94,
                1.0,
            )

            # Planned maintenance blocks.
            for _ in range(3):
                start_idx = self.rng.integers(0, self.time.n_hours - 48)
                duration = int(self.rng.integers(8, 36))
                values[start_idx:start_idx + duration] *= self.rng.uniform(0.05, 0.35)

            availability[asset.asset_id] = values

        return availability

    def solar_capacity_factor(self, irradiance: np.ndarray) -> np.ndarray:
        return np.clip(
            irradiance * self.rng.normal(0.97, 0.015, len(irradiance)),
            0,
            1,
        )

    @staticmethod
    def wind_capacity_factor(speed: np.ndarray) -> np.ndarray:
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
            ],
        )
        return np.clip(cf, 0, 0.95)

    def generate(
        self,
        assets: pd.DataFrame,
        weather: pd.DataFrame,
    ) -> pd.DataFrame:
        availability = self.build_availability(assets)
        irradiance = weather["solar_irradiance_index"].to_numpy()
        wind_speed = weather["wind_speed_mps"].to_numpy()
        timestamps = self.time.timestamps

        generation_rows = []

        for _, asset in assets.iterrows():
            if asset.technology == "Solar PV":
                cf = self.solar_capacity_factor(irradiance)
            else:
                cf = self.wind_capacity_factor(wind_speed)

            potential = (
                asset.capacity_mw
                * cf
                * availability[asset.asset_id]
            )

            for i, ts in enumerate(timestamps):
                generation_rows.append(
                    {
                        "timestamp": ts,
                        "asset_id": asset.asset_id,
                        "capacity_mw": asset.capacity_mw,
                        "availability_pct": availability[asset.asset_id][i] * 100,
                        "capacity_factor": cf[i],
                        "potential_generation_mwh": potential[i],
                    }
                )

        return pd.DataFrame(generation_rows)


# ============================================================================
# 5. SYSTEM OPERATIONS MODEL
# ============================================================================


class SystemOperationsModel:
    """Generates demand, grid constraints, BESS dispatch, EMS and market data."""

    BESS_CONFIG = {
        "North": {"power_mw": 50, "energy_mwh": 200},
        "Central": {"power_mw": 50, "energy_mwh": 200},
    }

    def __init__(self, config: GreenGridConfig, time: TimeContext, rng):
        self.config = config
        self.time = time
        self.rng = rng

    def generate_demand(self) -> np.ndarray:
        hours = self.time.hours
        days = self.time.days
        weekdays = self.time.weekdays
        n_hours = self.time.n_hours

        morning_peak = 95 * np.exp(-((hours - 8) / 2.7) ** 2)
        evening_peak = 170 * np.exp(-((hours - 19) / 3.0) ** 2)
        midday_load = 65 * np.exp(-((hours - 13) / 4.5) ** 2)

        weekday_multiplier = np.where(weekdays < 5, 1.0, 0.82)

        season_multiplier = (
            1 + 0.07 * np.sin(2 * np.pi * (days - 30) / 365)
        )

        demand = (
            310
            + morning_peak
            + evening_peak
            + midday_load
        ) * weekday_multiplier * season_multiplier

        demand += self.rng.normal(0, 14, n_hours)

        weekend_midday = (
            (weekdays >= 5)
            & (hours >= 10)
            & (hours <= 15)
            & (self.rng.random(n_hours) < 0.35)
        )

        demand[weekend_midday] *= self.rng.uniform(
            0.82,
            0.93,
            weekend_midday.sum(),
        )

        return np.clip(demand, 180, None)

    def generate_grid(self) -> pd.DataFrame:
        hours = self.time.hours
        days = self.time.days
        timestamps = self.time.timestamps
        n_hours = self.time.n_hours

        north_limit = np.full(n_hours, 80.0)
        central_limit = np.full(n_hours, 220.0)

        # Scheduled / forced transmission constraints.
        for region, limit in [
            ("North", north_limit),
            ("Central", central_limit),
        ]:
            for _ in range(16):
                start_idx = int(self.rng.integers(0, n_hours - 12))
                duration = int(self.rng.integers(2, 12))

                reduction = self.rng.choice(
                    [0.72, 0.82, 0.90],
                    p=[0.25, 0.50, 0.25],
                )

                limit[start_idx:start_idx + duration] *= reduction

        # North midday constraint during high-solar months.
        north_solar_constraint = (
            (hours >= 10)
            & (hours <= 15)
            & (days >= 90)
            & (days <= 280)
        )
        north_limit[north_solar_constraint] *= 0.75

        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "north_export_limit_mw": north_limit,
                "central_export_limit_mw": central_limit,
            }
        )

    def _regional_potential(
        self,
        potential_generation: pd.DataFrame,
        assets: pd.DataFrame,
    ):
        potential_by_asset = potential_generation.merge(
            assets[["asset_id", "region", "technology"]],
            on="asset_id",
            how="left",
        )

        regional_potential = (
            potential_by_asset.groupby(
                ["timestamp", "region"],
                as_index=False,
            )["potential_generation_mwh"].sum()
        )

        potential_pivot = regional_potential.pivot(
            index="timestamp",
            columns="region",
            values="potential_generation_mwh",
        ).fillna(0)

        return (
            potential_pivot["North"].to_numpy(),
            potential_pivot["Central"].to_numpy(),
        )

    def generate_bess(
        self,
        potential_generation: pd.DataFrame,
        assets: pd.DataFrame,
        demand: np.ndarray,
        grid: pd.DataFrame,
    ) -> pd.DataFrame:
        north_potential, central_potential = self._regional_potential(
            potential_generation,
            assets,
        )

        north_demand = demand * 0.45
        central_demand = demand * 0.55

        north_limit = grid["north_export_limit_mw"].to_numpy()
        central_limit = grid["central_export_limit_mw"].to_numpy()

        bess_rows = []
        soc_state = {
            "North": 170.0,
            "Central": 150.0,
        }

        for i, ts in enumerate(self.time.timestamps):
            for region in ["North", "Central"]:
                cfg = self.BESS_CONFIG[region]
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

                pre_bess_surplus = max(
                    potential_region - demand_region - export_limit,
                    0,
                )

                charge_request = 0
                if 9 <= ts.hour <= 15 and pre_bess_surplus > 0:
                    charge_request = min(power, pre_bess_surplus)

                available_room = max(energy - soc_state[region], 0)
                charge = min(charge_request, available_room / 0.94)
                soc_state[region] += charge * 0.94

                discharge_request = 0
                if 17 <= ts.hour <= 22:
                    discharge_request = min(
                        power * 0.75,
                        max(demand_region - potential_region, 0),
                    )

                discharge = min(
                    discharge_request,
                    soc_state[region] * 0.92,
                )
                soc_state[region] -= discharge / 0.92
                soc_state[region] = np.clip(
                    soc_state[region],
                    0,
                    energy,
                )

                bess_rows.append(
                    {
                        "timestamp": ts,
                        "region": region,
                        "battery_power_capacity_mw": power,
                        "battery_energy_capacity_mwh": energy,
                        "soc_mwh": soc_state[region],
                        "charge_mwh": charge,
                        "discharge_mwh": discharge,
                    }
                )

        return pd.DataFrame(bess_rows)

    def dispatch(
        self,
        potential_generation: pd.DataFrame,
        assets: pd.DataFrame,
        demand: np.ndarray,
        grid: pd.DataFrame,
        bess_clean: pd.DataFrame,
    ) -> pd.DataFrame:
        north_potential, central_potential = self._regional_potential(
            potential_generation,
            assets,
        )

        north_demand = demand * 0.45
        central_demand = demand * 0.55
        north_limit = grid["north_export_limit_mw"].to_numpy()
        central_limit = grid["central_export_limit_mw"].to_numpy()

        # Keep the same grouping logic as V2.1.
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

        north_absorption = north_demand + north_limit + north_charge
        central_absorption = central_demand + central_limit + central_charge

        north_actual = np.minimum(north_potential, north_absorption)
        central_actual = np.minimum(central_potential, central_absorption)

        north_curtailment = np.maximum(north_potential - north_actual, 0)
        central_curtailment = np.maximum(central_potential - central_actual, 0)

        return pd.DataFrame(
            {
                "timestamp": self.time.timestamps,
                "north_potential": north_potential,
                "central_potential": central_potential,
                "north_demand": north_demand,
                "central_demand": central_demand,
                "north_limit": north_limit,
                "central_limit": central_limit,
                "north_charge": north_charge,
                "central_charge": central_charge,
                "north_soc": bess_hourly["north_soc_mwh"].to_numpy(),
                "central_soc": bess_hourly["central_soc_mwh"].to_numpy(),
                "north_actual": north_actual,
                "central_actual": central_actual,
                "north_curtailment": north_curtailment,
                "central_curtailment": central_curtailment,
            }
        )

    def allocate_actual_generation(
        self,
        potential_generation: pd.DataFrame,
        assets: pd.DataFrame,
        dispatch: pd.DataFrame,
    ) -> pd.DataFrame:
        df = potential_generation.copy()
        df["region"] = df["asset_id"].map(
            assets.set_index("asset_id")["region"]
        )
        df["actual_generation_mwh"] = 0.0
        df["curtailment_mwh"] = 0.0

        dispatch_by_timestamp = dispatch.set_index("timestamp")

        for region in ["North", "Central"]:
            region_mask = df["region"] == region

            region_potential = (
                df.loc[region_mask]
                .groupby("timestamp")["potential_generation_mwh"]
                .transform("sum")
            )

            region_curtailment = dispatch_by_timestamp.loc[
                df.loc[region_mask, "timestamp"],
                "north_curtailment" if region == "North" else "central_curtailment",
            ].to_numpy()

            current_rows = df.loc[region_mask]
            shares = np.divide(
                current_rows["potential_generation_mwh"].to_numpy(),
                region_potential.to_numpy(),
                out=np.zeros(len(current_rows)),
                where=region_potential.to_numpy() > 0,
            )

            allocated_curtailment = shares * region_curtailment
            actual = (
                current_rows["potential_generation_mwh"].to_numpy()
                - allocated_curtailment
            )

            df.loc[region_mask, "curtailment_mwh"] = allocated_curtailment
            df.loc[region_mask, "actual_generation_mwh"] = actual

        return df

    def classify_reason(self, timestamp, region: str, dispatch: pd.DataFrame) -> str:
        row = dispatch.loc[dispatch["timestamp"] == timestamp].iloc[0]
        potential_region = row["north_potential"] if region == "North" else row["central_potential"]
        demand_region = row["north_demand"] if region == "North" else row["central_demand"]
        export = row["north_limit"] if region == "North" else row["central_limit"]
        charge = row["north_charge"] if region == "North" else row["central_charge"]

        if potential_region <= demand_region + export + charge + 1e-9:
            return "none"

        normal_export = 80 if region == "North" else 220

        if export < normal_export * 0.93:
            return "grid_constraint"

        if (
            10 <= timestamp.hour <= 15
            and potential_region > demand_region
            and charge >= self.BESS_CONFIG[region]["power_mw"] * 0.95
        ):
            return "storage_constraint"

        if potential_region > demand_region + export:
            return "low_demand_surplus"

        return "system_balancing"

    def build_ems(
        self,
        potential_generation: pd.DataFrame,
        demand: np.ndarray,
        dispatch: pd.DataFrame,
    ) -> pd.DataFrame:
        hourly_generation = (
            potential_generation.groupby("timestamp", as_index=False)
            .agg(
                potential_renewable_mwh=("potential_generation_mwh", "sum"),
                actual_renewable_mwh=("actual_generation_mwh", "sum"),
                curtailment_mwh=("curtailment_mwh", "sum"),
            )
        )

        ems = hourly_generation.copy()
        ems["total_demand_mwh"] = demand
        ems["potential_surplus_mwh"] = np.maximum(
            ems["potential_renewable_mwh"] - ems["total_demand_mwh"],
            0,
        )
        ems["actual_surplus_mwh"] = np.maximum(
            ems["actual_renewable_mwh"] - ems["total_demand_mwh"],
            0,
        )
        ems["renewable_share_pct"] = (
            ems["actual_renewable_mwh"]
            / ems["total_demand_mwh"]
            * 100
        )
        ems["net_load_mwh"] = (
            ems["total_demand_mwh"] - ems["actual_renewable_mwh"]
        )
        ems["north_export_limit_mw"] = dispatch["north_limit"].to_numpy()
        ems["central_export_limit_mw"] = dispatch["central_limit"].to_numpy()
        ems["north_potential_mwh"] = dispatch["north_potential"].to_numpy()
        ems["central_potential_mwh"] = dispatch["central_potential"].to_numpy()
        ems["north_curtailment_mwh"] = dispatch["north_curtailment"].to_numpy()
        ems["central_curtailment_mwh"] = dispatch["central_curtailment"].to_numpy()
        ems["system_stress_flag"] = (
            (ems["curtailment_mwh"] > 50)
            | (ems["potential_surplus_mwh"] > 100)
        ).astype(int)
        return ems

    def build_market(self, ems: pd.DataFrame) -> pd.DataFrame:
        hours = self.time.hours
        n_hours = self.time.n_hours

        price = (
            70
            + 12 * np.sin(2 * np.pi * (hours - 7) / 24)
            - 0.06 * ems["potential_surplus_mwh"].to_numpy()
            + self.rng.normal(0, 5, n_hours)
        )
        price = np.clip(price, -30, 180)

        negative_period = (
            (ems["potential_surplus_mwh"] > 200)
            & (self.rng.random(n_hours) < 0.35)
        )
        price[negative_period] = self.rng.uniform(
            -15,
            -1,
            negative_period.sum(),
        )

        return pd.DataFrame(
            {
                "timestamp": self.time.timestamps,
                "market_price_usd_per_mwh": np.round(price, 2),
            }
        )

    def build_dispatch_log(self, dispatch: pd.DataFrame) -> pd.DataFrame:
        event_rows = []
        event_id = 1

        for region, values in [
            ("North", dispatch["north_curtailment"].to_numpy()),
            ("Central", dispatch["central_curtailment"].to_numpy()),
        ]:
            active = values > 0.01
            start_idx = None

            for i in range(self.time.n_hours + 1):
                is_active = i < self.time.n_hours and active[i]

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
                            self.classify_reason(self.time.timestamps[j], region, dispatch)
                            for j in range(start_idx, end_idx + 1)
                        ]
                        reason = pd.Series(reasons).value_counts().index[0]

                        event_rows.append(
                            {
                                "event_id": f"CE-{event_id:05d}",
                                "region": region,
                                "start_time": self.time.timestamps[start_idx],
                                "end_time": self.time.timestamps[end_idx],
                                "duration_hours": end_idx - start_idx + 1,
                                "severity": severity,
                                "reason": reason,
                                "curtailed_energy_mwh": energy,
                                "operator_action": "Dispatch down renewable output",
                            }
                        )
                        event_id += 1

                    start_idx = None

        return pd.DataFrame(event_rows)

    def build_clean_truth(self, ems: pd.DataFrame) -> pd.DataFrame:
        clean_truth = ems[
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
        return clean_truth


# ============================================================================
# 6. RAW EXTRACT BUILDER
# ============================================================================


class RawExtractBuilder:
    """Creates clean source-system extracts before data-quality injection."""

    @staticmethod
    def build(
        assets: pd.DataFrame,
        potential_generation: pd.DataFrame,
        ems: pd.DataFrame,
        bess: pd.DataFrame,
        weather: pd.DataFrame,
        market: pd.DataFrame,
        dispatch: pd.DataFrame,
    ) -> Dict[str, pd.DataFrame]:
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

        ems_raw = ems.copy()
        ems_raw["source_system"] = "EMS"
        ems_raw["demand_unit"] = "MWh"
        ems_raw["record_status"] = "VALID"

        bess_raw = bess.copy()
        bess_raw["source_system"] = "BESS_CONTROLLER"
        bess_raw["record_status"] = "VALID"

        weather_raw = weather.copy()
        weather_raw["source_system"] = "WEATHER_STATION"
        weather_raw["record_status"] = "VALID"

        market_raw = market.copy()
        market_raw["source_system"] = "MARKET_FEED"
        market_raw["record_status"] = "VALID"

        dispatch_raw = dispatch.copy()
        dispatch_raw["source_system"] = "DISPATCH_LOG"
        dispatch_raw["record_status"] = "VALID"

        asset_raw = assets.copy()
        asset_raw["source_system"] = "ASSET_REGISTRY"

        return {
            "asset_registry_raw": asset_raw,
            "scada_generation_raw": scada_clean,
            "ems_operations_raw": ems_raw,
            "bess_operations_raw": bess_raw,
            "weather_station_raw": weather_raw,
            "market_price_raw": market_raw,
            "dispatch_curtailment_log_raw": dispatch_raw,
        }


# ============================================================================
# 7. DATA QUALITY INJECTION
# ============================================================================


class DataQualityInjector:
    """Injects the same intentional raw-data issues used by V2.1."""

    def __init__(self, seed: int, rng):
        self.seed = seed
        self.rng = rng
        self.issue_log: List[dict] = []

    def record_issue(self, table, issue_type, column, count, description):
        self.issue_log.append(
            {
                "table": table,
                "issue_type": issue_type,
                "column": column,
                "affected_records": int(count),
                "description": description,
            }
        )

    def inject_duplicates(self, df, table, fraction=0.002):
        if len(df) < 100:
            return df
        count = max(2, int(len(df) * fraction))
        dup = df.sample(count, random_state=self.seed)
        self.record_issue(
            table,
            "duplicate_rows",
            "multiple_columns",
            count,
            "Exact duplicate records inserted to simulate repeated source extraction.",
        )
        return pd.concat([df, dup], ignore_index=True)

    def inject_missing(self, df, table, column, fraction=0.002):
        count = max(2, int(len(df) * fraction))
        count = min(count, len(df))
        idx = self.rng.choice(df.index, count, replace=False)
        df.loc[idx, column] = np.nan
        self.record_issue(
            table,
            "missing_values",
            column,
            count,
            "Random operational readings removed from raw extract.",
        )
        return df

    def inject_category_noise(self, df, table, column, fraction=0.01):
        if column not in df.columns:
            return df
        valid_idx = df.index[df[column].notna()]
        if len(valid_idx) == 0:
            return df
        count = min(max(2, int(len(df) * fraction)), len(valid_idx))
        idx = self.rng.choice(valid_idx, count, replace=False)
        df[column] = df[column].astype("object")
        for i in idx:
            value = str(df.loc[i, column])
            df.loc[i, column] = self.rng.choice(
                [value.upper(), value.lower(), f" {value}", f"{value} "]
            )
        self.record_issue(
            table,
            "inconsistent_categories",
            column,
            count,
            "Capitalization and whitespace variations inserted.",
        )
        return df

    def inject_timestamp_noise(self, df, table, fraction=0.004):
        if "timestamp" not in df.columns:
            return df
        count = max(2, int(len(df) * fraction))
        count = min(count, len(df))
        idx = self.rng.choice(df.index, count, replace=False)
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%Y/%m/%d %H:%M",
            "%m-%d-%Y %H:%M",
        ]
        df["timestamp"] = df["timestamp"].astype("object")
        for i in idx:
            ts = pd.to_datetime(df.loc[i, "timestamp"])
            df.loc[i, "timestamp"] = ts.strftime(self.rng.choice(formats))
        self.record_issue(
            table,
            "timestamp_format",
            "timestamp",
            count,
            "Multiple timestamp formats inserted.",
        )
        return df

    def inject_numeric_as_text(self, df, table, column, fraction=0.003):
        if column not in df.columns:
            return df
        valid_idx = df.index[df[column].notna()]
        if len(valid_idx) == 0:
            return df
        count = min(max(2, int(len(df) * fraction)), len(valid_idx))
        idx = self.rng.choice(valid_idx, count, replace=False)
        df[column] = df[column].astype("object")
        for i in idx:
            value = df.loc[i, column]
            df.loc[i, column] = str(value)
        self.record_issue(
            table,
            "numeric_as_text",
            column,
            count,
            "Numeric values stored as strings in source extract.",
        )
        return df

    def inject_dispatch_timestamp_noise(self, df, table, fraction=0.01):
        if df.empty:
            return df
        for column in ["start_time", "end_time"]:
            if column not in df.columns:
                continue
            count = min(max(1, int(len(df) * fraction)), len(df))
            idx = self.rng.choice(df.index, count, replace=False)
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%d/%m/%Y %H:%M",
                "%Y/%m/%d %H:%M",
                "%m-%d-%Y %H:%M",
            ]
            df[column] = df[column].astype("object")
            for i in idx:
                ts = pd.to_datetime(df.loc[i, column])
                df.loc[i, column] = ts.strftime(self.rng.choice(formats))
            self.record_issue(
                table,
                "timestamp_format",
                column,
                count,
                "Multiple timestamp formats inserted into dispatch event timestamps.",
            )
        return df

    def apply(self, tables: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        scada_raw = self.inject_duplicates(tables["scada_generation_raw"].copy(), "scada_generation_raw")
        scada_raw = self.inject_missing(scada_raw, "scada_generation_raw", "actual_generation_mwh", 0.003)
        scada_raw = self.inject_missing(scada_raw, "scada_generation_raw", "availability_pct", 0.002)
        scada_raw = self.inject_timestamp_noise(scada_raw, "scada_generation_raw")
        scada_raw = self.inject_numeric_as_text(scada_raw, "scada_generation_raw", "actual_generation_mwh")

        outlier_idx = self.rng.choice(scada_raw.index, 6, replace=False)
        scada_raw.loc[outlier_idx[:3], "actual_generation_mwh"] = -5
        scada_raw.loc[outlier_idx[3:], "actual_generation_mwh"] = 999
        self.record_issue(
            "scada_generation_raw",
            "physical_outlier",
            "actual_generation_mwh",
            6,
            "Impossible negative or above-capacity generation readings inserted.",
        )

        ems_raw = self.inject_duplicates(tables["ems_operations_raw"].copy(), "ems_operations_raw")
        ems_raw = self.inject_missing(ems_raw, "ems_operations_raw", "total_demand_mwh", 0.002)
        ems_raw = self.inject_timestamp_noise(ems_raw, "ems_operations_raw")
        ems_raw = self.inject_numeric_as_text(ems_raw, "ems_operations_raw", "total_demand_mwh")

        unit_idx = self.rng.choice(
            ems_raw.index,
            max(4, int(len(ems_raw) * 0.001)),
            replace=False,
        )
        ems_raw.loc[unit_idx, "demand_unit"] = "MW"
        self.record_issue(
            "ems_operations_raw",
            "unit_inconsistency",
            "demand_unit",
            len(unit_idx),
            "A small number of records use MW while the operational field is hourly MWh.",
        )

        bess_raw = self.inject_duplicates(tables["bess_operations_raw"].copy(), "bess_operations_raw")
        bess_raw = self.inject_missing(bess_raw, "bess_operations_raw", "soc_mwh", 0.003)
        bess_raw = self.inject_timestamp_noise(bess_raw, "bess_operations_raw")
        bess_raw = self.inject_category_noise(bess_raw, "bess_operations_raw", "region")

        bess_outliers = self.rng.choice(bess_raw.index, 8, replace=False)
        bess_raw.loc[bess_outliers[:4], "soc_mwh"] = -10
        bess_raw.loc[bess_outliers[4:], "soc_mwh"] = 999
        self.record_issue(
            "bess_operations_raw",
            "physical_outlier",
            "soc_mwh",
            8,
            "SOC values outside battery energy capacity inserted.",
        )

        weather_raw = self.inject_duplicates(tables["weather_station_raw"].copy(), "weather_station_raw")
        weather_raw = self.inject_missing(weather_raw, "weather_station_raw", "wind_speed_mps", 0.004)
        weather_raw = self.inject_timestamp_noise(weather_raw, "weather_station_raw")

        weather_outliers = self.rng.choice(weather_raw.index, 6, replace=False)
        weather_raw.loc[weather_outliers[:3], "wind_speed_mps"] = -2
        weather_raw.loc[weather_outliers[3:], "wind_speed_mps"] = 60
        self.record_issue(
            "weather_station_raw",
            "physical_outlier",
            "wind_speed_mps",
            6,
            "Negative and implausibly high wind-speed readings inserted.",
        )

        market_raw = self.inject_duplicates(tables["market_price_raw"].copy(), "market_price_raw")
        market_raw = self.inject_missing(market_raw, "market_price_raw", "market_price_usd_per_mwh", 0.002)
        market_raw = self.inject_timestamp_noise(market_raw, "market_price_raw")
        market_raw = self.inject_numeric_as_text(market_raw, "market_price_raw", "market_price_usd_per_mwh")

        dispatch_raw = tables["dispatch_curtailment_log_raw"].copy()
        if len(dispatch_raw) > 5:
            dispatch_raw = self.inject_duplicates(
                dispatch_raw,
                "dispatch_curtailment_log_raw",
                fraction=0.01,
            )
            dispatch_raw = self.inject_category_noise(
                dispatch_raw,
                "dispatch_curtailment_log_raw",
                "reason",
                fraction=0.02,
            )
            dispatch_raw = self.inject_missing(
                dispatch_raw,
                "dispatch_curtailment_log_raw",
                "reason",
                fraction=0.015,
            )
            dispatch_raw = self.inject_dispatch_timestamp_noise(
                dispatch_raw,
                "dispatch_curtailment_log_raw",
                fraction=0.01,
            )

        asset_raw = self.inject_category_noise(
            tables["asset_registry_raw"].copy(),
            "asset_registry_raw",
            "region",
            fraction=0.15,
        )
        asset_raw = self.inject_category_noise(
            asset_raw,
            "asset_registry_raw",
            "technology",
            fraction=0.15,
        )

        return {
            "asset_registry_raw": asset_raw,
            "scada_generation_raw": scada_raw,
            "ems_operations_raw": ems_raw,
            "bess_operations_raw": bess_raw,
            "weather_station_raw": weather_raw,
            "market_price_raw": market_raw,
            "dispatch_curtailment_log_raw": dispatch_raw,
        }


# ============================================================================
# 8. VALIDATION AND OUTPUT
# ============================================================================


class OutputManager:
    """Writes raw data, reference data, metadata, and console KPI summary."""

    def __init__(self, config: GreenGridConfig):
        self.config = config
        for folder in [config.raw_dir, config.ref_dir, config.meta_dir]:
            folder.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def calculate_kpis(clean_truth: pd.DataFrame) -> dict:
        total_potential = clean_truth["potential_renewable_mwh"].sum()
        total_actual = clean_truth["actual_renewable_mwh"].sum()
        total_curtailment = clean_truth["curtailment_mwh"].sum()
        curtailment_rate = total_curtailment / total_potential
        total_potential_surplus = clean_truth["potential_surplus_mwh"].sum()
        total_actual_surplus = clean_truth["actual_surplus_mwh"].sum()
        peak_curtailment = clean_truth["curtailment_mwh"].max()
        hours_curtailed = (clean_truth["curtailment_mwh"] > 0.01).sum()
        high_curtailment_hours = (clean_truth["curtailment_mwh"] > 100).sum()
        north_curt = clean_truth["north_curtailment_mwh"].sum()
        central_curt = clean_truth["central_curtailment_mwh"].sum()

        return {
            "total_potential": total_potential,
            "total_actual": total_actual,
            "total_curtailment": total_curtailment,
            "curtailment_rate": curtailment_rate,
            "total_potential_surplus": total_potential_surplus,
            "total_actual_surplus": total_actual_surplus,
            "peak_curtailment": peak_curtailment,
            "hours_curtailed": hours_curtailed,
            "high_curtailment_hours": high_curtailment_hours,
            "north_curt": north_curt,
            "central_curt": central_curt,
        }

    def write_raw_tables(self, tables: Dict[str, pd.DataFrame]):
        for name, df in tables.items():
            df.to_csv(self.config.raw_dir / f"{name}.csv", index=False)

    def write_reference(
        self,
        clean_truth: pd.DataFrame,
        kpis: dict,
        issue_log: List[dict],
    ):
        expected_kpis = pd.DataFrame(
            {
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
                    kpis["total_potential"],
                    kpis["total_actual"],
                    kpis["total_curtailment"],
                    kpis["curtailment_rate"],
                    kpis["total_potential_surplus"],
                    kpis["total_actual_surplus"],
                    kpis["peak_curtailment"],
                    kpis["hours_curtailed"],
                    kpis["high_curtailment_hours"],
                ],
            }
        )
        expected_kpis["value"] = expected_kpis["value"].round(3)
        expected_kpis.to_csv(self.config.ref_dir / "expected_kpis.csv", index=False)

        pd.DataFrame(issue_log).to_csv(
            self.config.ref_dir / "data_quality_issue_log.csv",
            index=False,
        )
        clean_truth.to_csv(
            self.config.ref_dir / "clean_truth_hourly.csv",
            index=False,
        )

    def write_metadata(self, assets: pd.DataFrame):
        metadata = f"""
GREEN GRID ENERGY — SYNTHETIC DATASET V2.1

Period:
{self.config.start} to {self.config.end}

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
        (self.config.meta_dir / "README_generator.txt").write_text(
            metadata,
            encoding="utf-8",
        )

    def print_summary(self, time: TimeContext, assets: pd.DataFrame, kpis: dict):
        north_share = (
            kpis["north_curt"] / kpis["total_curtailment"] * 100
            if kpis["total_curtailment"] > 0
            else 0.0
        )

        print("\n" + "=" * 72)
        print("GREEN GRID ENERGY — SYNTHETIC DATASET V2.1 (REFACTORED)")
        print("=" * 72)
        print(f"Period                  : {self.config.start} → {self.config.end}")
        print(f"Hourly observations     : {time.n_hours:,}")
        print(f"Renewable assets        : {len(assets)}")
        print(f"Potential generation    : {kpis['total_potential']:,.0f} MWh")
        print(f"Actual generation       : {kpis['total_actual']:,.0f} MWh")
        print(f"Curtailed energy        : {kpis['total_curtailment']:,.0f} MWh")
        print(f"Curtailment rate        : {kpis['curtailment_rate']:.2f}%")
        print(f"Potential surplus       : {kpis['total_potential_surplus']:,.0f} MWh")
        print(f"Actual surplus          : {kpis['total_actual_surplus']:,.0f} MWh")
        print(f"North curtailment       : {kpis['north_curt']:,.0f} MWh")
        print(f"Central curtailment     : {kpis['central_curt']:,.0f} MWh")
        print(f"North curtailment share : {north_share:.1f}%")
        print(f"Curtailed hours         : {kpis['hours_curtailed']:,}")
        print(f"High-curtailment hours  : {kpis['high_curtailment_hours']:,}")
        print("-" * 72)
        print(f"RAW DATA                : {self.config.raw_dir.resolve()}")
        print(f"REFERENCE               : {self.config.ref_dir.resolve()}")
        print(f"METADATA                : {self.config.meta_dir.resolve()}")
        print("=" * 72)


# ============================================================================
# 9. ORCHESTRATION
# ============================================================================


class GreenGridPipeline:
    """Coordinates the end-to-end synthetic data generation workflow."""

    def __init__(self, config: GreenGridConfig | None = None):
        self.config = config or GreenGridConfig()
        self.rng = np.random.default_rng(self.config.seed)
        self.time = TimeContext(self.config)

        self.asset_builder = AssetRegistryBuilder()
        self.weather_generator = WeatherStationGenerator(
            self.config,
            self.time,
            self.rng,
        )
        self.generation_model = RenewableGenerationModel(
            self.config,
            self.time,
            self.rng,
        )
        self.operations_model = SystemOperationsModel(
            self.config,
            self.time,
            self.rng,
        )
        self.raw_builder = RawExtractBuilder()
        self.dq_injector = DataQualityInjector(
            self.config.seed,
            self.rng,
        )
        self.output_manager = OutputManager(self.config)

    def run(self):
        print(f"Generating {self.time.n_hours:,} hourly timestamps...")

        # 1. Asset master.
        assets = self.asset_builder.build()

        # 2. Weather/resource observations.
        weather = self.weather_generator.generate()

        # 3. Renewable potential generation.
        potential_generation = self.generation_model.generate(assets, weather)

        # 4. Demand and grid constraints.
        demand = self.operations_model.generate_demand()
        grid = self.operations_model.generate_grid()

        # 5. BESS operation.
        bess_clean = self.operations_model.generate_bess(
            potential_generation,
            assets,
            demand,
            grid,
        )

        # 6. System dispatch and curtailment.
        dispatch = self.operations_model.dispatch(
            potential_generation,
            assets,
            demand,
            grid,
            bess_clean,
        )

        potential_generation = self.operations_model.allocate_actual_generation(
            potential_generation,
            assets,
            dispatch,
        )

        # 7. Cause classification is performed after allocation, matching V2.1.
        potential_generation["curtailment_reason"] = "none"
        for region in ["North", "Central"]:
            mask = potential_generation["region"] == region
            potential_generation.loc[mask, "curtailment_reason"] = [
                self.operations_model.classify_reason(ts, region, dispatch)
                for ts in potential_generation.loc[mask, "timestamp"]
            ]

        # 8. EMS, market, and event log.
        ems_clean = self.operations_model.build_ems(
            potential_generation,
            demand,
            dispatch,
        )
        market_clean = self.operations_model.build_market(ems_clean)
        dispatch_clean = self.operations_model.build_dispatch_log(dispatch)
        clean_truth = self.operations_model.build_clean_truth(ems_clean)

        # 9. Clean source extracts.
        clean_tables = self.raw_builder.build(
            assets,
            potential_generation,
            ems_clean,
            bess_clean,
            weather,
            market_clean,
            dispatch_clean,
        )

        # 10. Inject raw-data quality issues.
        raw_tables = self.dq_injector.apply(clean_tables)

        # 11. Write outputs and references.
        self.output_manager.write_raw_tables(raw_tables)
        kpis = self.output_manager.calculate_kpis(clean_truth)
        self.output_manager.write_reference(
            clean_truth,
            kpis,
            self.dq_injector.issue_log,
        )
        self.output_manager.write_metadata(assets)
        self.output_manager.print_summary(self.time, assets, kpis)

        # Fail loudly if the core reconciliation is broken.
        max_error = clean_truth["reconciliation_check_mwh"].abs().max()
        if max_error > 1e-9:
            raise ValueError(
                f"Clean-truth reconciliation failed: max error = {max_error} MWh"
            )

        return {
            "assets": assets,
            "weather": weather,
            "potential_generation": potential_generation,
            "bess_clean": bess_clean,
            "ems_clean": ems_clean,
            "market_clean": market_clean,
            "dispatch_clean": dispatch_clean,
            "clean_truth": clean_truth,
            "raw_tables": raw_tables,
            "kpis": kpis,
        }


# ============================================================================
# 10. ENTRY POINT
# ============================================================================


if __name__ == "__main__":
    GreenGridPipeline().run()
