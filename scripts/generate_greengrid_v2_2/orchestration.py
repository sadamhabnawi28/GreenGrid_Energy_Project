from configuration import GreenGridConfig, TimeContext
from asset_master import AssetRegistryBuilder
from weather import WeatherStationGenerator
from renewable_generation_model import RenewableGenerationModel
from system_operation_model import SystemOperationsModel
from raw_extract_builder import RawExtractBuilder
from data_quality_injector import DataQualityInjector
from validation_and_output import OutputManager
import numpy as np

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

# if __name__ == "__main__":
#     GreenGridPipeline().run()
