from dataclasses import dataclass
from pathlib import Path
import pandas as pd


@dataclass(frozen=True)
class GreenGridConfig:
    seed: int = 42
    start: str = "2025-01-01 00:00:00"
    end: str = "2025-12-31 23:00:00"
    base_dir: Path = Path("datasets/greengrid_v2_2")

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
