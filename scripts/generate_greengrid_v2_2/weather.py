from configuration import GreenGridConfig, TimeContext
import numpy as np
import pandas as pd

class WeatherStationGenerator:
    """Generates weather/resource observations used by renewable assets."""

    def __init__(self, config: GreenGridConfig, time: TimeContext, rng):
        self.config = config
        self.time = time
        self.rng = rng

    def irradiance(self, days, hours, n_hours):
        """Solar irradiance: daylight curve + seasonality + cloud events + noise."""

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
        
        return np.clip(
                    solar_day_curve * solar_season * cloud_factor,
                    0,
                    1.05,
                )

    def wind_speed(self, days, hours, n_hours):
        """Wind resource."""
        wind_speed = (
                    7.0
                    + 1.3 * np.sin(2 * np.pi * (days - 40) / 365)
                    + 1.0 * np.sin(2 * np.pi * hours / 24 + 1.2)
                    + self.rng.normal(0, 1.3, n_hours)
                )
        return np.clip(wind_speed, 1.0, 16.0)

    def temperature(self, days, hours, n_hours):
        temperature = (
                    27
                    + 3.5 * np.sin(2 * np.pi * (hours - 14) / 24)
                    + 1.8 * np.sin(2 * np.pi * days / 365)
                    + self.rng.normal(0, 1.2, n_hours)
                )
        return temperature

    def generate(self) -> pd.DataFrame:
        hours = self.time.hours
        days = self.time.days
        n_hours = self.time.n_hours
        timestamps = self.time.timestamps

        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "station_id": "WX-MASTER",
                "solar_irradiance_index": np.round(self.irradiance(days, hours, n_hours), 4),
                "wind_speed_mps": np.round(self.wind_speed(days, hours, n_hours), 3),
                "temperature_c": np.round(self.temperature(days, hours, n_hours), 2),
            }
        )