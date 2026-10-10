from configuration import GreenGridConfig, TimeContext
from typing import Dict, List
import pandas as pd

# ============================================================================
# 8. VALIDATION AND OUTPUT
# ============================================================================


class ValidationManager:
    """Validates raw schema and confirms the V2.1 business KPI truth is preserved."""

    EXPECTED_V21_KPIS = {
        "total_potential": 1790631.898,
        "total_actual": 1770878.903,
        "total_curtailment": 19752.995,
        "curtailment_rate": 1.103,
        "total_potential_surplus": 227548.161,
        "total_actual_surplus": 207795.166,
        "peak_curtailment": 195.747,
        "hours_curtailed": 633,
        "high_curtailment_hours": 16,
    }

    @staticmethod
    def validate_raw_schema(raw_tables: Dict[str, pd.DataFrame]):
        """Ensure derived analysis fields are absent from source-oriented raw tables."""
        forbidden = {
            "weather_station_raw": {"cloud_cover_pct"},
            "scada_generation_raw": {
                "capacity_factor", "potential_generation_mwh",
                "actual_generation_mwh", "curtailment_mwh",
            },
            "ems_operations_raw": {
                "potential_renewable_mwh", "actual_renewable_mwh",
                "curtailment_mwh", "potential_surplus_mwh",
                "actual_surplus_mwh", "renewable_share_pct",
                "net_load_mwh", "north_potential_mwh",
                "central_potential_mwh", "north_curtailment_mwh",
                "central_curtailment_mwh", "system_stress_flag",
            },
            "bess_operations_raw": {"soc_mwh"},
            "dispatch_curtailment_log_raw": {
                "duration_hours", "severity", "curtailed_energy_mwh",
            },
        }
        violations = []
        for table, cols in forbidden.items():
            present = sorted(set(raw_tables[table].columns) & cols)
            if present:
                violations.append(f"{table}: {present}")
        if violations:
            raise ValueError(
                "Derived columns leaked into source-oriented raw outputs: "
                + "; ".join(violations)
            )

    @classmethod
    def validate_kpis(cls, actual: dict, tolerance: float = 0.001):
        failures = []
        for key, expected in cls.EXPECTED_V21_KPIS.items():
            observed = actual[key]
            if key in {"hours_curtailed", "high_curtailment_hours"}:
                ok = observed == expected
            else:
                ok = abs(observed - expected) <= tolerance
            if not ok:
                failures.append((key, observed, expected))
        if failures:
            raise ValueError(f"V2.1 KPI preservation validation failed: {failures}")
        return True

    @staticmethod
    def validate_reconciliation(clean_truth: pd.DataFrame, tolerance: float = 1e-9):
        max_error = clean_truth["reconciliation_check_mwh"].abs().max()
        if max_error > tolerance:
            raise ValueError(
                f"Clean-truth reconciliation failed: max error = {max_error} MWh"
            )
        return max_error


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
        curtailment_rate = total_curtailment / total_potential * 100
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
GREEN GRID ENERGY — SYNTHETIC DATASET V2.2

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

REGIONAL DEMAND ALLOCATION:
    North demand = 45% of total system demand
    Central demand = 55% of total system demand

This is an explicit synthetic modeling assumption used by the existing
BESS and dispatch logic, now exposed in ems_operations_raw.csv so regional
analysis can use the same demand allocation. It is not measured regional
demand; replace it with regional meter/EMS measurements in a real deployment.

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
        print("GREEN GRID ENERGY — SYNTHETIC DATASET V2.2 (SOURCE-FIRST RAW DATA)")
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
