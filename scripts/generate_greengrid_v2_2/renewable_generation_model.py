from configuration import GreenGridConfig, TimeContext
from typing import Dict
import pandas as pd
import numpy as np

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