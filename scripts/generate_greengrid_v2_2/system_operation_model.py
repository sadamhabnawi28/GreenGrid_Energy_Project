from configuration import GreenGridConfig, TimeContext
import numpy as np
import pandas as pd

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