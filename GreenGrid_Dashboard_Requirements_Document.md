# GreenGrid Energy
## Dashboard Requirements Document (DRD)
**Project:** Renewable Curtailment & Energy Surplus Analysis  
**Document owner:** Data Manager, Energy Analytics  
**Assigned to:** Data Analyst  
**Version:** 1.0  
**Date:** 12 October 2026  
**Status:** Requirements baseline for dashboard development

---

## 1. Assignment from the Data Manager

You are assigned to design, build, validate, and document a stakeholder dashboard that explains **when, where, and under what operating conditions renewable generation is curtailed or exceeds local demand**, and supports decisions to reduce avoidable curtailment.

The dashboard must not stop at describing the problem. It must help Energy Management, Grid Operations, Asset Operations, and Commercial/Finance teams determine:

1. How much renewable generation was potentially available, how much was modelled as utilized, and how much was modelled as curtailed?
2. When and where do surplus and curtailment occur most frequently and severely?
3. Which regions, technologies, and assets are associated with the largest modelled curtailment?
4. How do demand, export limits, BESS operation/state of charge, weather, market prices, and dispatch-event records relate to these outcomes?
5. What operational interventions should be investigated first, and what evidence should be monitored to assess them?

**Important:** This dashboard is an operational decision-support product built from a modelled dataset. It must label modelled estimates clearly and must not present them as metered generation, verified causal attribution, or actual financial loss.

## 2. Business background and problem statement

GreenGrid Energy operates a renewable portfolio containing solar PV and wind assets across the **North** and **Central** regions. Renewable output varies with weather and can at times exceed local demand and the energy that can be exported through grid connections. Storage can shift energy over time, but its ability to absorb surplus depends on charging power, available energy capacity, state of charge, efficiency, and operating constraints.

When the system cannot absorb or export all available renewable energy, some potential generation may be curtailed. This can reduce renewable-energy utilization and may create an economic opportunity cost. However, the value of curtailed energy depends on market prices, contracts, settlement rules, compensation arrangements, and whether the generation could actually have been sold or used.

The current analysis pipeline estimates potential generation using weather proxies and asset availability, estimates regional absorption, allocates modelled curtailment to assets, and joins market prices and dispatch-event context. The dashboard must make those assumptions visible.

### 2.1 Primary business question

**How can GreenGrid identify the timing, location, and operating conditions associated with renewable surplus and modelled curtailment, then prioritize operational or investment actions to improve renewable utilization?**

### 2.2 Supporting business questions

- Which months, days, and hours show the highest potential surplus and modelled curtailment?
- Is the problem concentrated in North or Central?
- Which technologies and assets contribute most to modelled curtailment?
- How often does a surplus/curtailment event occur, and how severe is it?
- Are events associated with export limits, demand patterns, BESS charging/discharging or reconstructed SOC, weather conditions, negative prices, or dispatch-log reasons?
- What is the indicative market value of modelled curtailed energy under the observed hourly price series?
- Which periods warrant operational review, and what additional data is required before committing to a mitigation investment?

## 3. Stakeholders and decisions supported

| Stakeholder | Primary questions | Decisions supported |
|---|---|---|
| Energy Management | When and where does potential generation exceed demand or absorption? | Dispatch planning, operating strategy, flexibility needs |
| Grid Operations | Are export limits or network constraints associated with events? | Constraint investigation, export-capacity coordination, operating procedures |
| Asset Operations | Which assets/technologies have the highest modelled curtailment? | Asset-level review, availability and performance investigation |
| BESS / Storage Operations | Is storage charging when surplus occurs, and what is its reconstructed SOC? | Charging-window review, storage dispatch optimization, data-quality follow-up |
| Commercial / Finance | What is the indicative market value associated with modelled curtailed MWh? | Prioritization of commercial analysis; not financial-loss booking |
| Leadership / Portfolio Management | Is the problem material, where is it concentrated, and what should be investigated first? | Prioritization of studies, operating changes, or investment cases |
| Data / Analytics | Are metrics traceable, reproducible, and sufficiently reliable? | Data-quality remediation and model improvement |

## 4. Scope

### 4.1 In scope

- Hourly analysis across the available 2025 period (8,760 hourly timestamps, subject to source completeness).
- System, regional, technology, and asset-level views.
- Potential generation, modelled actual generation, modelled curtailment, surplus, demand, export capacity, BESS operation, weather proxies, market price, and dispatch-event context.
- Time-series analysis, rankings, event investigation, and operational drill-down.
- Transparent definitions, data-quality indicators, and model caveats.
- North-versus-Central comparison.
- A concise decision-oriented summary and a prioritized investigation backlog.

### 4.2 Out of scope unless source data is added

- Claiming metered actual generation or verified curtailment as fact.
- Determining legally or contractually recognized lost revenue.
- Proving causal root causes from correlations or dispatch-log text alone.
- Dispatch optimization, power-flow simulation, grid stability analysis, or a production-grade battery control algorithm.
- CO₂ savings or fossil displacement calculations without a defined counterfactual and emissions factors.
- Forecasting future curtailment unless a separately validated forecast model is developed.
- Investment ROI/payback calculations without CAPEX, OPEX, contractual, and operational inputs.

## 5. Data sources and technical baseline

Use the existing cleaned source tables and the three generated analysis outputs from the current GreenGrid pipeline.

### 5.1 Required outputs

| File | Grain | Intended dashboard use |
|---|---|---|
| `greengrid_system_hourly_kpis.csv` | One row per timestamp/hour | Executive overview and system-wide trends |
| `greengrid_regional_hourly_kpis.csv` | One row per timestamp and region | North/Central comparison and regional constraints |
| `greengrid_asset_hour_analysis.csv` | One row per asset and timestamp/hour | Asset/technology drill-down and event investigation |

### 5.2 Key fields expected in the outputs

**System-hourly file**
- `timestamp`
- `system_potential_generation_mwh`
- `system_modeled_actual_generation_mwh`
- `system_modeled_curtailment_mwh`
- `total_demand_mwh`
- `north_demand_mwh`, `central_demand_mwh`
- `potential_surplus_mwh`, `modeled_actual_surplus_mwh`
- `net_load_mwh`, `renewable_share_pct`
- `system_curtailment_rate_pct`, `system_stress_flag`
- `market_price_usd_per_mwh`, `negative_market_price_flag`
- `indicative_curtailment_value_usd`
- `curtailment_value_positive_price_usd`
- `curtailment_value_at_negative_price_usd`

**Regional-hourly file**
- `timestamp`, `region`
- `regional_potential_generation_mwh`, `asset_count`
- `regional_demand_mwh`
- `export_limit_mw`, `export_capacity_mwh`
- `battery_power_capacity_mw`, `battery_energy_capacity_mwh`
- `charge_mwh`, `discharge_mwh`, `soc_mwh_reconstructed`
- `regional_absorption_capacity_mwh`
- `modeled_actual_generation_mwh`, `modeled_curtailment_mwh`
- `regional_curtailment_rate_pct`, `regional_surplus_mwh`
- `regional_bess_net_energy_mwh`
- `dispatch_event_count`, `dispatch_event_ids`, `dispatch_reasons`

**Asset-hour file**
- Asset descriptors: `asset_id`, `asset_name`, `technology`, `region`, `grid_node`, `capacity_mw`
- Weather/availability: `availability_pct`, `availability_factor`, `station_id`, `solar_irradiance_index`, `wind_speed_mps`, optional `temperature_c`
- Asset metrics: `modeled_capacity_factor`, `potential_generation_mwh`, `modeled_actual_generation_mwh`, `allocated_curtailment_mwh`, `asset_curtailment_rate_pct`, `asset_potential_share_pct`
- Regional/system context: corresponding regional/system metrics and demand fields
- Market context: `market_price_usd_per_mwh`, value proxies
- Dispatch context: `dispatch_event_count`, `dispatch_event_ids`, `dispatch_reasons`

The Analyst must inspect the actual schemas before development and handle optional columns safely. Do not silently replace missing fields with zero unless zero is a valid business value.

### 5.3 Source-of-truth and grain rules

1. Use the **system-hourly output** for system-level KPI cards and trends.
2. Use the **regional-hourly output** for regional comparisons.
3. Use the **asset-hour output** for asset/technology detail.
4. Do not sum repeated system or regional metrics from the asset-hour table: the same hourly/regional values are repeated across assets and would be double-counted.
5. Keep `timestamp` at hourly grain and standardize it to a single timezone. Document whether the timestamps are UTC or local time before publishing.
6. Use `asset_id` and `region` as stable keys. Do not join weather data to SCADA on timestamp alone when multiple stations exist; preserve the validated asset-to-station mapping.
7. The three outputs must reconcile before dashboard measures are published.

## 6. KPI catalogue and definitions

Use the following definitions consistently across every page. Where a metric is an estimate, include “modelled” or “indicative” in its displayed name or tooltip.

### 6.1 Core system KPIs

| KPI | Definition / formula | Unit | Why stakeholders need it |
|---|---|---:|---|
| Potential renewable generation | Sum of `system_potential_generation_mwh` | MWh | Estimated renewable energy that could have been generated under the modelled weather and availability assumptions |
| Modelled actual renewable generation | Sum of `system_modeled_actual_generation_mwh` | MWh | Estimated renewable energy remaining after the modelled curtailment allocation |
| Modelled curtailed energy | Sum of `system_modeled_curtailment_mwh` | MWh | Main indicator of the scale of renewable energy not absorbed in the model |
| Modelled curtailment rate | Total modelled curtailed MWh ÷ total potential renewable MWh × 100 | % | Normalizes curtailment against available potential generation; aggregate as a ratio of sums, not an average of hourly percentages |
| Renewable utilization rate | Modelled actual renewable MWh ÷ potential renewable MWh × 100 | % | Indicates the share of modelled potential generation that is utilized; mathematically equals 100% minus curtailment rate when definitions reconcile and denominator is non-zero |
| Potential surplus energy | Sum of `potential_surplus_mwh` | MWh | Measures hours in which modelled potential generation exceeds total demand; it is not automatically equal to curtailment |
| Modelled actual surplus energy | Sum of `modeled_actual_surplus_mwh` | MWh | Shows estimated generation above demand after modelled curtailment; useful for understanding residual surplus |
| Surplus hours | Count of distinct hourly timestamps where `potential_surplus_mwh > 0` | hours | Measures frequency, not just total volume |
| Curtailment hours | Count of distinct hourly timestamps where `system_modeled_curtailment_mwh > 0` | hours | Indicates how often curtailment appears in the model |
| Average curtailment per curtailed hour | Total modelled curtailed MWh ÷ number of curtailed hours | MWh/hour | Indicates typical severity during affected hours |
| Renewable share of demand | Modelled actual renewable MWh ÷ total demand MWh × 100 | % | Contextualizes renewable contribution to demand; flag values over 100% rather than capping them silently |
| Net load | Total demand MWh − modelled actual renewable generation MWh | MWh | Negative values indicate modelled renewable generation exceeds demand; positive values indicate residual demand beyond renewable output |
| Stress hours | Count of hours where `system_stress_flag = 1` | hours | Quick indicator based on the current model's thresholds; threshold sensitivity should be documented |

**Aggregation rule:** percentage KPIs must be recomputed from summed numerators and denominators for the selected filter context. Do not average hourly rates unless the label explicitly says “average hourly rate.”

### 6.2 Regional, asset, and technology KPIs

| KPI | Definition / formula | Unit | Why stakeholders need it |
|---|---|---:|---|
| Regional potential generation | Sum of `regional_potential_generation_mwh` by region | MWh | Compares estimated renewable opportunity across North and Central |
| Regional modelled curtailment | Sum of `modeled_curtailment_mwh` by region | MWh | Identifies which region contributes most to the modelled issue |
| Regional curtailment rate | Regional modelled curtailed MWh ÷ regional potential MWh × 100 | % | Fairer comparison between regions of different size |
| Regional surplus energy | Sum of `regional_surplus_mwh` | MWh | Highlights local potential generation exceeding regional demand; it is not necessarily exportable surplus |
| Asset modelled curtailment | Sum of `allocated_curtailment_mwh` by asset | MWh | Prioritizes assets for investigation; allocation is proportional, not asset-metered |
| Asset curtailment rate | Sum of allocated curtailed MWh ÷ sum of potential generation MWh × 100 | % | Compares relative impact across assets |
| Technology share of modelled curtailment | Technology modelled curtailed MWh ÷ system modelled curtailed MWh × 100 | % | Shows whether solar or wind contributes more to the total modelled volume |
| Asset potential share | Potential generation of asset ÷ regional potential generation × 100 | % | Context for the asset's share of regional potential; not a performance score |
| Export utilization proxy | Modelled actual generation ÷ (regional demand + export capacity) × 100, only if the denominator and interpretation are appropriate | % | Optional diagnostic only; not a physical line loading metric and must not be described as actual export utilization |

**Important grain rule:** the regional `modeled_curtailment_mwh` repeated in the asset-hour output must never be summed across assets. Use `allocated_curtailment_mwh` for asset-level totals and the regional table for regional totals.

### 6.3 BESS and grid-constraint metrics

| KPI | Definition / formula | Unit | Why stakeholders need it |
|---|---|---:|---|
| BESS charge energy | Sum of `charge_mwh` | MWh | Indicates how much energy storage absorbed during the period |
| BESS discharge energy | Sum of `discharge_mwh` | MWh | Indicates energy delivered from storage |
| BESS net energy proxy | Sum of `discharge_mwh - charge_mwh` (`regional_bess_net_energy_mwh`) | MWh | Positive means net discharge; negative means net charging under the field convention |
| Reconstructed SOC | `soc_mwh_reconstructed` at the selected hour | MWh | Context for whether the model estimates storage as relatively full or empty |
| SOC percentage proxy | Reconstructed SOC ÷ battery energy capacity × 100 | % | Easier comparison across storage sizes; only show when capacity and SOC are valid |
| Export capacity energy equivalent | `export_limit_mw × interval_hours` | MWh per interval | Converts the hourly export limit into an hourly energy equivalent; does not establish actual export |
| Dispatch-event hours | Count of distinct region-hours with one or more dispatch events | hours | Helps identify when recorded operational interventions coincide with modelled events |
| Dispatch event count | Count of unique event IDs in the relevant period | events | Quantifies logged events, not necessarily independent causal incidents |
| Curtailment during dispatch-event hours | Modelled curtailed MWh during hours with a dispatch event | MWh | Descriptive association only; does not prove the event caused the curtailment |

Do not infer unused storage capacity from charge energy alone. A proper “available charging headroom” metric requires validated SOC, charge power limits, battery constraints, and a clearly defined time-step model.

### 6.4 Market and indicative economic metrics

| KPI | Definition / formula | Unit | Why stakeholders need it |
|---|---|---:|---|
| Weighted average market price | Sum of hourly price × chosen energy basis ÷ sum of that energy basis; state whether basis is demand, modelled actual generation, or another measure | USD/MWh | Provides price context without an unweighted mean across hours |
| Indicative curtailment value | Sum of `system_modeled_curtailment_mwh × market_price_usd_per_mwh` | USD | Scenario indicator for the market value associated with modelled curtailed energy, not recognized lost revenue |
| Indicative value at positive prices | Sum of curtailed MWh × price for hours where price > 0 | USD | Separates periods with positive hourly market prices |
| Indicative value at negative prices | Sum of curtailed MWh × price for hours where price < 0 | USD | Makes negative-price periods visible; a negative result is not a loss estimate |
| Negative-price hours | Count of hours where `market_price_usd_per_mwh < 0` | hours | Identifies periods when additional generation may have low or negative spot-market value |
| Curtailment during negative-price hours | Sum of modelled curtailed MWh in hours with price < 0 | MWh | Helps assess the price context of curtailment |
| Curtailment during positive-price hours | Sum of modelled curtailed MWh in hours with price > 0 | MWh | Helps prioritize further commercial/contract analysis |

Economic values must be described as **indicative market-value proxies**. They are not actual revenue, verified lost revenue, compensation due, or profit impact. Commercial interpretation requires PPAs, settlement rules, curtailment compensation, imbalance costs, fees, and the applicable market-price definition.

### 6.5 Event and diagnostic metrics

- **Dispatch reason mix:** count of dispatch events grouped by `dispatch_reasons`; show missing/unknown separately.
- **Curtailment by dispatch reason:** modelled curtailed MWh during hours associated with each reason, clearly labelled as “curtailment during event hours,” not “curtailment caused by reason.”
- **Surplus-to-curtailment relationship:** compare hourly potential surplus with modelled curtailment; explain that surplus and curtailment are different concepts and may not match one-to-one.
- **Weather context:** compare solar irradiance proxy or wind speed with potential generation and modelled curtailment. These are exploratory associations, not proof of cause.
- **Availability context:** trend or scatter plot of availability against potential generation/curtailment; verify that availability values are valid and interpret them within the model.
- **Data-quality indicators:** missing hours, duplicate keys, unmapped weather stations, invalid ranges, and reconciliation failures.

## 7. Dashboard information architecture

Build a multi-page dashboard with consistent navigation, shared filters, clear metric definitions, and drill-through from summary to diagnostic detail. The exact platform may be Power BI or Tableau, but the output must satisfy the functional and visual requirements below.

### Page 1 — Executive Overview

**Purpose:** Give leadership a concise answer to “How material is the modelled curtailment problem, and where should we investigate first?”

**Required visuals**
1. KPI cards: Potential generation, modelled actual generation, modelled curtailed MWh, modelled curtailment rate, surplus hours, curtailment hours, and indicative curtailment value.
2. Hourly or daily time series: potential generation vs modelled actual generation, with modelled curtailment displayed separately.
3. Monthly trend: modelled curtailment MWh and curtailment rate.
4. Region comparison: North vs Central for modelled curtailed MWh, curtailment rate, and surplus MWh.
5. Event/diagnostic summary: dispatch-event hours and negative-price hours.
6. A short “Key findings / investigations to prioritize” text panel, generated from validated findings and not hard-coded to unverified causal claims.

**Interactions**
- Selecting a month, region, or technology should filter related visuals where the data model supports it.
- Clicking a region should navigate to the Regional Operations page.
- KPI cards must show units, period, and whether a value is modelled or indicative.

### Page 2 — Temporal Pattern & Surplus

**Purpose:** Identify when surplus and curtailment happen.

**Required visuals**
1. Hour-of-day × month heatmap for modelled curtailment MWh or curtailment frequency.
2. Hour-of-day × day-of-week heatmap for potential surplus or curtailment frequency.
3. Daily trend for potential surplus MWh, modelled actual surplus MWh, and modelled curtailed MWh.
4. Distribution of hourly curtailment values (for example, histogram or severity bands).
5. Top 10 dates/hours by modelled curtailed MWh and by potential surplus MWh.
6. Comparison of modelled curtailment with market price, using separate axes or a scatter plot that avoids misleading scales.

**Questions this page must answer**
- Are events clustered in certain months or hours?
- Is the issue frequent but small, or rare but severe?
- Are large-curtailment hours also hours with positive or negative market prices?

### Page 3 — Regional Operations & Grid Constraints

**Purpose:** Compare North and Central and investigate the relationship between demand, export limits, storage, and curtailment.

**Required visuals**
1. Regional KPI cards or a comparison table for potential generation, demand, surplus, modelled curtailed MWh, and curtailment rate.
2. Regional time series: potential generation, demand, export capacity energy equivalent, modelled actual generation, and curtailment.
3. Scatter plot: regional potential generation vs regional demand, coloured by curtailment rate or event presence.
4. BESS charge/discharge trend by region.
5. Reconstructed SOC trend with battery energy capacity shown as a reference.
6. Dispatch-event timeline or table including timestamp, region, event ID, reason, operator action if available, and modelled curtailment during the associated hour.
7. Ranked table of region-hours with high modelled curtailment, high surplus, export limits, SOC, and dispatch context.

**Required caution:** `regional_absorption_capacity_mwh` is based on a simplified model and includes observed charge energy. It is not a validated physical measure of how much energy the grid and storage could absorb. The page must label it “modelled absorption capacity (proxy)” if shown.

### Page 4 — Asset & Technology Performance

**Purpose:** Identify where modelled curtailment is allocated and which assets warrant review.

**Required visuals**
1. Technology comparison for potential generation, modelled actual generation, allocated curtailed MWh, and curtailment rate.
2. Asset ranking table with asset ID/name, technology, region, capacity, potential MWh, modelled actual MWh, allocated curtailed MWh, and asset curtailment rate.
3. Bar chart of top assets by allocated curtailed MWh.
4. Scatter plot: asset potential generation vs allocated curtailment, with technology/region encoded.
5. Asset-hour detail table for selected assets and dates, including weather proxies, availability, potential generation, allocated curtailment, price, and dispatch context.

**Rules**
- Use `allocated_curtailment_mwh` for asset-level curtailment totals.
- State that asset curtailment is allocated in proportion to potential generation within each region-hour; it is not an asset-level metered or dispatch-verified measure.
- Do not label an asset as underperforming solely because its allocated curtailment is high; capacity, technology, location, and operating context differ.

### Page 5 — Market Context & Indicative Value

**Purpose:** Provide a cautious view of the price context around modelled curtailment.

**Required visuals**
1. KPI cards: indicative value proxy, positive-price value proxy, negative-price value proxy, negative-price hours.
2. Monthly trend of modelled curtailed MWh and indicative value proxy.
3. Scatter plot of hourly market price vs modelled curtailed MWh.
4. Table of highest-curtailment hours with timestamp, region/system curtailment, market price, and value proxy.
5. Clear methodology note explaining why this is not recognized lost revenue.

**Decision use:** Identify hours or seasons for follow-up with Commercial/Finance; do not use the dashboard alone to claim realized financial loss or justify an investment.

### Page 6 — Data Quality & Model Assumptions

**Purpose:** Let analysts and managers understand how much confidence to place in the results.

**Required components**
1. Data completeness by table and period.
2. Duplicate-key checks for system timestamp, regional timestamp+region, and asset timestamp+asset ID.
3. Missing weather, asset-to-station mapping, missing price, invalid availability, and invalid capacity checks.
4. Reconciliation: system potential generation vs sum of asset potential generation by hour; system curtailment vs sum of asset allocated curtailment; regional totals vs system totals where comparable.
5. A model assumptions panel covering the weather proxy, wind curve, regional demand allocation if used, reconstructed SOC, regional absorption proxy, proportional asset curtailment allocation, stress-flag thresholds, and indicative market-value formula.
6. A status indicator: Pass / Warning / Fail, with clear thresholds and explanation.

This page may be hidden from casual executive navigation but must be accessible to analysts and data owners.

## 8. Required dashboard filters and interactions

### 8.1 Global filters

- Date range (minimum granularity: date; underlying data remains hourly).
- Month and year, if supported by the time dimension.
- Region: North / Central.
- Technology: Solar PV / Wind.
- Asset name or asset ID.
- Dispatch reason, including Unknown / Missing.
- Negative vs non-negative market-price category.
- Curtailment/surplus event flag.

Only show a filter on pages where it is relevant. Global filters must not create confusing or misleading cross-filter behavior across different grains.

### 8.2 Drill-down and drill-through

- System → Region → Asset → Hour/event detail.
- Month → day → hour.
- Region → dispatch event context.
- Asset selection must filter asset-specific measures but must not cause system totals to be summed from repeated asset-hour rows.
- Provide a “Reset filters” control and a visible indicator of active filters.

### 8.3 Tooltips

At minimum, tooltips should provide:
- Metric definition and unit.
- Selected period and region/asset where applicable.
- Numerator and denominator for rate KPIs.
- “Modelled estimate” or “Indicative proxy” label where applicable.
- Data-quality or assumption warning when relevant.

## 9. Data model and calculation implementation

### 9.1 Recommended semantic model

Use separate fact tables by grain rather than flattening all metrics into one table for all calculations:

- `FactSystemHourly`: one row per timestamp.
- `FactRegionalHourly`: one row per timestamp + region.
- `FactAssetHourly`: one row per timestamp + asset ID.
- Optional `FactDispatchEvent`: one row per event, if the source event-level file is available and validated.
- `DimDateTime`: date, year, quarter, month, day, day of week, hour, and relevant time labels.
- `DimAsset`: asset ID, name, technology, region, grid node, capacity, and asset status.
- Optional `DimRegion`, `DimTechnology`, and `DimDispatchReason`.

Use shared dimensions where appropriate. Do not create a many-to-many relationship that duplicates facts. If the BI tool requires relationships across different grains, document and test their filter behavior.

### 9.2 Measures versus columns

- Use source columns for stable row-level values and derived measures where aggregation must respond to filters.
- Implement aggregate rates as measures using sums of numerator and denominator.
- Avoid pre-aggregating rates and then averaging them.
- Keep the difference between **potential surplus** and **modelled curtailment** visible throughout the dashboard.
- Keep **modelled actual generation** separate from measured generation.
- Any additional calculated field must have a documented formula, unit, grain, and validation test.

### 9.3 Core measure logic

Illustrative pseudocode (adapt to Power BI DAX, Tableau calculations, or the selected platform):

```text
Potential Generation (MWh) =
    SUM(FactSystemHourly[system_potential_generation_mwh])

Modelled Actual Generation (MWh) =
    SUM(FactSystemHourly[system_modeled_actual_generation_mwh])

Modelled Curtailment (MWh) =
    SUM(FactSystemHourly[system_modeled_curtailment_mwh])

Modelled Curtailment Rate (%) =
    DIVIDE(
        [Modelled Curtailment (MWh)],
        [Potential Generation (MWh)]
    ) * 100

Renewable Utilization Rate (%) =
    DIVIDE(
        [Modelled Actual Generation (MWh)],
        [Potential Generation (MWh)]
    ) * 100

Surplus Hours =
    DISTINCTCOUNT of timestamps where potential_surplus_mwh > 0

Curtailment Hours =
    DISTINCTCOUNT of timestamps where system_modeled_curtailment_mwh > 0

Indicative Curtailment Value (USD) =
    SUM(FactSystemHourly[indicative_curtailment_value_usd])
```

The conditional hour counts should be implemented as filter-aware measures, not as a count of rows from the asset-hour fact. Use the selected period and filter context consistently.

## 10. Visual design and accessibility requirements

- Prioritize a clean operational design: summary first, diagnostics second, detailed records last.
- Use consistent colors across pages: potential generation, modelled actual generation, curtailment, surplus, demand, BESS charging, and BESS discharging must each have consistent meanings.
- Do not rely on color alone; use labels, legends, or symbols.
- Use line charts for time series, bars for ranked comparisons, heatmaps for temporal concentration, and tables for detailed event investigation.
- Avoid dual-axis charts unless clearly justified and labelled.
- Use consistent units: MWh for hourly energy, MW for power limits/capacity, USD/MWh for price, USD for value proxies, and % for rates.
- Display the reporting period, last refresh time, and model/data status.
- Include metric definitions in tooltips or a definitions panel.
- Use accessible contrast, readable font sizes, descriptive chart titles, and meaningful sorting.
- Default view should show the full 2025 reporting period only if all required data is available and validated; otherwise show the verified period and clearly indicate missing periods.

## 11. Data-quality, reconciliation, and validation requirements

Before publishing, the Analyst must complete and record the following checks.

### 11.1 Structural checks

- System fact has at most one row per timestamp.
- Regional fact has at most one row per timestamp + region.
- Asset fact has at most one row per timestamp + asset ID.
- Expected hours are checked against the calendar; 2025 is expected to contain 8,760 hourly timestamps in a non-leap year, but actual completeness must be verified.
- Asset IDs, region names, technology values, and timestamps are standardized.
- Asset-to-weather-station mapping is complete and unique where weather is used.

### 11.2 Metric checks

- `system_potential_generation_mwh` reconciles to the sum of asset `potential_generation_mwh` for each timestamp within an agreed tolerance.
- `system_modeled_curtailment_mwh` reconciles to the sum of asset `allocated_curtailment_mwh` for each timestamp within an agreed tolerance.
- Regional totals reconcile to system totals where the measures have equivalent definitions.
- `allocated_curtailment_mwh` is not negative and does not exceed `potential_generation_mwh` beyond a small numerical tolerance.
- Rates use valid denominators and handle zero/blank values explicitly.
- Market-value proxy reconciles to modelled curtailed MWh multiplied by the applicable hourly price.
- Dispatch-event counts are based on unique event IDs, not duplicated event-hour rows.
- Negative market prices remain negative; do not replace them with zero.

### 11.3 Model validation and warning labels

- Confirm the weather irradiance index scale and the wind-speed proxy are suitable for the generated data before interpreting the capacity factor.
- Validate that the demand allocation (45% North / 55% Central) is a synthetic assumption if source regional demand is unavailable; surface this prominently.
- Reconstructed SOC is not measured SOC and must not be used as a control-system value.
- The regional absorption-capacity calculation is a simplified proxy; observed charge energy is not equivalent to available charging headroom.
- Proportional asset curtailment allocation is an allocation rule, not proof of which asset was curtailed.
- Dispatch reasons are operational context, not independently verified root causes.
- Economic values are indicative market-value proxies, not actual lost revenue.
- The stress flag uses the current model thresholds (`system_modeled_curtailment_mwh > 50 MWh` OR `potential_surplus_mwh > 100 MWh` per hour). The dashboard must display these thresholds or link to the methodology note.

If a reconciliation fails, do not suppress the discrepancy. Display a warning, investigate the cause, and block publication of affected metrics until the issue is understood.

## 12. Known model limitations to disclose

1. **Potential generation is modelled.** Solar output uses an irradiance proxy; wind output uses a simplified piecewise curve. These are not manufacturer power curves or validated production estimates.
2. **Actual generation is modelled, not metered.** The source SCADA file does not contain a measured MWh field in the current pipeline.
3. **Curtailment is modelled.** It is inferred from a simplified regional absorption calculation and allocated to assets in proportion to potential generation.
4. **Regional demand may be allocated synthetically.** If the EMS source does not provide regional demand, the pipeline allocates total demand 45% to North and 55% to Central. Regional insights then depend on this assumption.
5. **Storage SOC is reconstructed.** It is calculated sequentially from charge/discharge energy, efficiencies, and initial SOC; it is not the battery's recorded SOC.
6. **Grid absorption is simplified.** The model does not fully represent network topology, actual export flow, battery charge headroom, ramp limits, or dispatch priority.
7. **Dispatch records are not causal proof.** Event overlap with curtailment does not prove that the event caused the curtailment.
8. **Market value is indicative.** It excludes contracts, compensation, settlement, imbalance, and other commercial terms.

These limitations must be visible in the dashboard and the accompanying handover documentation.

## 13. Acceptance criteria

The dashboard is accepted only when all applicable items below pass.

### Functional acceptance
- [ ] All required pages are present and navigable.
- [ ] Global filters and page-level filters work as documented.
- [ ] Drill-through supports system → region → asset/hour investigation.
- [ ] Tooltips explain units, definitions, and modelled/indicative status.
- [ ] Reset filters and active-filter indicators work.
- [ ] Visuals respect the correct data grain and do not double-count repeated metrics.

### KPI acceptance
- [ ] KPI values reconcile to the output CSVs for a defined test period.
- [ ] Curtailed MWh and curtailment rate use consistent definitions.
- [ ] Potential surplus and modelled curtailment are not conflated.
- [ ] Regional and asset rankings use the correct fields.
- [ ] Indicative market values reconcile to hourly curtailed MWh × price.
- [ ] Conditional counts count distinct hours or unique events as specified.

### Data and model acceptance
- [ ] Structural and reconciliation tests are documented.
- [ ] Data-quality warnings are visible and actionable.
- [ ] Model assumptions and limitations are disclosed.
- [ ] Any added calculation includes a formula, unit, grain, and test.
- [ ] Missing or invalid data is not silently converted into valid-looking zeroes.

### Usability acceptance
- [ ] Executive page answers the primary business question at a glance.
- [ ] Charts have clear titles, labels, units, and legends.
- [ ] The dashboard is readable at the intended screen size.
- [ ] A stakeholder can identify a high-impact period, region, and asset and inspect its context without exporting the whole dataset.

### Handover acceptance
- [ ] Dashboard file/workbook is delivered.
- [ ] Data model and relationships are documented.
- [ ] KPI dictionary and assumptions are included.
- [ ] QA/reconciliation results are included.
- [ ] A short user guide explains filters, navigation, and interpretation.

## 14. Required deliverables from the Data Analyst

1. **Interactive dashboard** in the agreed BI platform.
2. **KPI dictionary** documenting each metric's name, business meaning, formula, unit, grain, source field, aggregation behavior, and caveat.
3. **Data model diagram** showing fact-table grains, dimensions, and relationships.
4. **QA and reconciliation log** with test, expected result, actual result, status, and remediation.
5. **Methodology and limitations note** visible from the dashboard or accompanying documentation.
6. **Stakeholder readout** with the most material patterns found, the evidence supporting them, the limitations, and prioritized follow-up actions.
7. **Technical handover** describing refresh steps, file dependencies, calculation logic, and known issues.

## 15. Recommended analysis-to-action framework

Use the dashboard to produce evidence-based follow-up questions, not unsupported root-cause declarations.

| Observed pattern | Investigation to initiate | Possible action to evaluate (not assume) |
|---|---|---|
| Curtailment clustered in certain hours | Compare demand, export limits, storage state/operation, market price, and dispatch logs for those hours | Adjust operating/charging windows, review dispatch procedures, or study flexible demand |
| One region dominates modelled curtailment | Validate regional demand allocation, export-limit records, asset mapping, and network constraint data | Grid/export study, regional flexibility assessment, or better regional metering |
| High allocated curtailment for an asset | Check allocation method, asset potential, availability, weather mapping, and asset-specific dispatch/meter data | Asset-level operational review; do not treat allocation alone as proof of underperformance |
| Curtailment coincides with high positive prices | Verify price series, contracts, actual generation, and settlement terms | Commercial/contract analysis and mitigation feasibility study |
| Curtailment coincides with negative prices | Review dispatch rationale and market participation rules | Assess whether curtailment was economically rational; do not assume it is avoidable |
| Storage appears underused during surplus | Validate SOC telemetry, charge power, capacity headroom, efficiency, operating restrictions, and location | Storage dispatch review or additional telemetry/modeling |
| Dispatch reasons recur during high-curtailment periods | Review event records with Grid Operations and verify event start/end times | Improve event coding and test specific operational interventions |

Every recommendation in the stakeholder readout must state: **observed evidence → interpretation → caveat → proposed validation/action → success metric**.

## 16. Suggested success measures after implementation

These are measures for future operational monitoring, not promises of improvement:

- Change in modelled curtailment MWh and rate, calculated on comparable periods.
- Change in surplus hours and average modelled curtailed MWh per curtailed hour.
- Change in curtailment during positive-price hours.
- Change in frequency of high-curtailment region-hours.
- Verified change in actual metered renewable utilization once measured generation data is available.
- Change in storage charging during validated surplus windows, subject to battery constraints and operating policy.
- Improved completeness of regional demand, SOC, asset-level generation, and dispatch-cause data.

Do not claim the dashboard itself caused a reduction in curtailment. Measure the outcome after an intervention and account for changes in weather, demand, prices, availability, and operating conditions.

---

## Appendix A — Minimum definitions shown to dashboard users

- **Potential generation:** modelled renewable generation estimated from capacity, weather proxy, availability, and interval length.
- **Modelled actual generation:** potential generation less modelled curtailment under the current methodology; not a meter reading.
- **Modelled curtailment:** estimated potential energy not absorbed under the modelled regional constraint.
- **Potential surplus:** modelled potential generation above demand; it does not imply that the energy was technically exportable or that all surplus was curtailed.
- **Modelled actual surplus:** modelled actual generation above demand; may remain positive after curtailment.
- **Asset allocated curtailment:** regional modelled curtailment distributed across assets in proportion to potential generation.
- **Reconstructed SOC:** sequential estimate of battery energy content based on initial SOC, charge/discharge energy, and efficiencies.
- **Indicative curtailment value:** modelled curtailed MWh multiplied by hourly market price; not actual lost revenue.
- **Dispatch-event association:** temporal overlap between event records and modelled curtailment; not proof of causality.

## Appendix B — Final instruction from the Data Manager

Prioritize **correctness, traceability, and decision usefulness over visual complexity**. A stakeholder should be able to move from a system-level signal to the relevant region, asset, hour, and operating context. If a metric cannot be supported reliably by the current data, disclose the limitation and recommend the data needed to support it rather than presenting a misleadingly precise number.
