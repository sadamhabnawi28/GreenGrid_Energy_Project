from typing import Dict, List
import pandas as pd
import numpy as np

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
        scada_raw = self.inject_missing(scada_raw, "scada_generation_raw", "availability_pct", 0.002)
        scada_raw = self.inject_timestamp_noise(scada_raw, "scada_generation_raw")
        scada_raw = self.inject_numeric_as_text(scada_raw, "scada_generation_raw", "availability_pct")

        outlier_idx = self.rng.choice(scada_raw.index, 6, replace=False)
        scada_raw.loc[outlier_idx[:3], "availability_pct"] = -5
        scada_raw.loc[outlier_idx[3:], "availability_pct"] = 150
        self.record_issue(
            "scada_generation_raw",
            "physical_outlier",
            "availability_pct",
            6,
            "Impossible negative or above-100% availability readings inserted.",
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
        bess_raw = self.inject_missing(bess_raw, "bess_operations_raw", "charge_mwh", 0.003)
        bess_raw = self.inject_timestamp_noise(bess_raw, "bess_operations_raw")
        bess_raw = self.inject_category_noise(bess_raw, "bess_operations_raw", "region")

        bess_outliers = self.rng.choice(bess_raw.index, 8, replace=False)
        bess_raw.loc[bess_outliers[:4], "charge_mwh"] = -10
        bess_raw.loc[bess_outliers[4:], "charge_mwh"] = 999
        self.record_issue(
            "bess_operations_raw",
            "physical_outlier",
            "charge_mwh",
            8,
            "Charge readings outside physically plausible hourly battery power limits inserted.",
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