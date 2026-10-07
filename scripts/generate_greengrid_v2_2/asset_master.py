import pandas as pd

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
