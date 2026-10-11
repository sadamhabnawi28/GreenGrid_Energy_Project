# GreenGrid Energy — Data Join & Operational KPI Pipeline

The pipeline builds an **asset-hour** fact table while preserving system-hour and region-hour grains for correct aggregation.

```mermaid
flowchart TB
  subgraph SRC[Cleaned source files]
    AR["asset_registry_clean.csv<br/>1 row / asset<br/>Key: asset_id"]
    SC["scada_generation_clean.csv<br/>1 row / asset-hour<br/>Key: asset_id + timestamp"]
    WX["weather_station_clean.csv<br/>1 row / station-hour<br/>Key: station_id + timestamp"]
    MAP["asset_weather_mapping.csv (optional if only 1 station)<br/>asset_id → station_id"]
    EMS["ems_operations_clean.csv<br/>1 row / hour<br/>Total/regional demand + export limits"]
    BES["bess_operations_clean.csv<br/>1 row / region-hour<br/>Battery charge/discharge/capacity"]
    MP["market_price_clean.csv<br/>1 row / hour<br/>Key: timestamp"]
    DL["dispatch_curtailment_log_clean.csv<br/>1 row / event<br/>region + start_time + end_time"]
  end

  subgraph BUILD[Asset-hour preparation]
    BASE["1. Asset-hour base<br/>SCADA LEFT JOIN asset registry<br/>ON asset_id<br/>Many-to-one"]
    WJOIN["2. Weather mapping + join<br/>Map station to each asset;<br/>join by timestamp + asset_id<br/>Do not join by timestamp alone"]
    POT["3. Potential generation estimate<br/>capacity × modeled capacity factor<br/>× availability × interval hours"]
  end

  subgraph REG[Regional-hour modeling]
    ER["Expand EMS to North/Central<br/>One row per timestamp + region<br/>Prefer regional demand; otherwise documented 45/55 split"]
    BF["BESS features<br/>One row per timestamp + region<br/>Reconstruct SOC (modeled)"]
    RM["4. Regional-hour model<br/>Potential generation aggregated by timestamp + region<br/>Join EMS + BESS on timestamp + region<br/>Calculate absorption capacity, modeled output & curtailment"]
    DE["5. Enrich with dispatch events<br/>Expand event start–end to hourly rows<br/>Aggregate by timestamp + region<br/>Append after regional KPI calculations; does not drive modeled curtailment"]
  end

  subgraph KPIS[Allocation and system metrics]
    AL["6. Allocate regional curtailment back to assets<br/>Join on timestamp + region (many-to-one)<br/>Allocate by asset's share of regional potential generation"]
    SYS["7. System-hour KPIs<br/>Aggregate asset-hour results by timestamp<br/>Join EMS + market price on timestamp<br/>Calculate surplus, renewable share, price/value proxies"]
  end

  subgraph OUT[Outputs]
    OA[("OUTPUT A<br/>greengrid_asset_hour_analysis.csv<br/>Grain: asset × hour")]
    OR[("OUTPUT B<br/>greengrid_regional_hourly_kpis.csv<br/>Grain: region × hour")]
    OS[("OUTPUT C<br/>greengrid_system_hourly_kpis.csv<br/>Grain: one row / hour")]
  end

  AR -->|asset_id| BASE
  SC -->|asset_id + timestamp grain| BASE
  BASE --> WJOIN
  WX -->|station_id + timestamp| WJOIN
  MAP -->|asset_id ↔ station_id| WJOIN
  WJOIN --> POT
  POT -->|aggregate potential by timestamp + region| RM
  EMS --> ER
  ER -->|timestamp + region| RM
  BES -->|timestamp + region| BF
  BF -->|timestamp + region| RM
  DL --> DE
  RM -->|regional metrics| AL
  RM -->|append event metadata after model calculations| DE
  POT -->|asset potential share| AL
  DE -->|regional KPIs + event count / IDs / reasons| OR
  AL --> SYS
  EMS -->|timestamp| SYS
  MP -->|timestamp| SYS
  AL --> OA
  DE -->|region-hour event fields| OA
  SYS -->|timestamp-level KPIs| OA
  SYS --> OS

  classDef gen fill:#e4eef8,stroke:#4d7ea8,color:#17324d;
  classDef wx fill:#e7f4e8,stroke:#50945d,color:#17324d;
  classDef ops fill:#fff1d6,stroke:#c28a24,color:#17324d;
  classDef mkt fill:#fce7f3,stroke:#b95a89,color:#17324d;
  class AR,SC,BASE,POT,AL,OA gen;
  class WX,MAP,WJOIN wx;
  class EMS,BES,ER,BF,RM,OR ops;
  class MP,DL,DE,SYS,OS mkt;
```

## Join rules and expected grain

| From | To | Join key / transformation | Join method and guardrail |
|---|---|---|---|
| SCADA | Asset registry | `asset_id` | `LEFT JOIN`; many SCADA rows per asset to one asset master row |
| Asset-hour base | Weather | `timestamp` + mapped `asset_id` (mapping contains `asset_id`, `station_id`) | Each asset must map to exactly one station in the script; weather itself is keyed by `station_id` + `timestamp` |
| Asset-hour potential generation | Regional model | Group by `timestamp`, `region` | Aggregate first; do not join raw asset rows directly to regional rows before aggregation |
| EMS | Regional model | Expand hourly EMS into North/Central rows; key `timestamp` + `region` | Prefer `north_demand_mwh` and `central_demand_mwh`; script falls back to 45%/55% if missing |
| BESS | Regional model | `timestamp` + `region` | One-to-one after checking the BESS grain is unique |
| Dispatch event log | Regional model / regional output | Expand `[start_time, end_time]` to hourly timestamps, then group by `timestamp` + `region` | Join the aggregated event-hour table, never the raw event log directly to asset-hour rows |
| Regional model | Asset-hour results | `timestamp` + `region` | Many asset-hour rows to one regional-hour row; curtailment allocated by potential-generation share |
| Asset-hour results | System KPI table | Group by `timestamp` | Aggregate to one row per hour before joining system inputs |
| EMS + market price | System KPI table | `timestamp` | One-to-one joins, after uniqueness checks |
| System KPI table | Asset-hour output | `timestamp` | Many asset-hour rows to one system-hour row; system KPIs repeat across assets in the same hour |

## Important interpretation note

`modeled_actual_generation_mwh`, `modeled_curtailment_mwh`, reconstructed battery SOC and market-value fields are model-based estimates. `market price × modeled curtailed MWh` is an indicative value proxy, not verified lost revenue or booked revenue. For total-system KPIs, use `greengrid_system_hourly_kpis.csv` to avoid summing repeated system values from the asset-hour output.
