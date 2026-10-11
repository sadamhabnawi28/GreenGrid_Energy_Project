
GREEN GRID ENERGY — SYNTHETIC DATASET V2

Period:
2025-01-01 00:00:00 to 2025-12-31 23:00:00

Resolution:
Hourly

Assets:
6

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
