import pandas as pd
from typing import Dict


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
            ]
        ].copy()
        scada_clean["source_system"] = "SCADA"
        scada_clean["reading_status"] = "VALID"

        ems_raw = ems[
            [
                "timestamp",
                "total_demand_mwh",
                "north_export_limit_mw",
                "central_export_limit_mw",
            ]
        ].copy()
        ems_raw["source_system"] = "EMS"
        ems_raw["demand_unit"] = "MWh"
        ems_raw["record_status"] = "VALID"

        bess_raw = bess[
            [
                "timestamp",
                "region",
                "battery_power_capacity_mw",
                "battery_energy_capacity_mwh",
                "charge_mwh",
                "discharge_mwh",
            ]
        ].copy()
        bess_raw["source_system"] = "BESS_CONTROLLER"
        bess_raw["record_status"] = "VALID"

        weather_raw = weather.copy()
        weather_raw["source_system"] = "WEATHER_STATION"
        weather_raw["record_status"] = "VALID"

        market_raw = market.copy()
        market_raw["source_system"] = "MARKET_FEED"
        market_raw["record_status"] = "VALID"

        dispatch_raw = dispatch[
            [
                "event_id",
                "region",
                "start_time",
                "end_time",
                "reason",
                "operator_action",
            ]
        ].copy()
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