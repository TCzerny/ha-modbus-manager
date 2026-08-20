# Grafana PV monitoring (InfluxQL)

Example Grafana dashboard for **Sungrow SHx** data recorded from Home Assistant into **InfluxDB** (InfluxQL, Grafana 10+ / 12). It is the packaged form of the local PV-Monitoring dashboard: live power, daily totals, energy flow, autarky, savings, and year comparison.

Battery values in this dashboard are **inverter hybrid registers** (`{PREFIX}_battery_level`, `{PREFIX}_battery_power`, …), not the separate SBR/SBH template. SBR cell dashboards stay in the Home Assistant YAML examples.

## Files

| File | Purpose |
|------|---------|
| [pv_monitoring.json](pv_monitoring.json) | Grafana dashboard JSON (import this) |

## Requirements

- Home Assistant **InfluxDB** integration writing entity states (default: measurement = unit, tag `entity_id` **without** domain, lowercase)
- Grafana with an **InfluxDB** datasource using **InfluxQL** (not Flux)
- Modbus Manager SHx hub with a device prefix (example: `SG` → Influx `sg_…`)

## Import

1. Grafana → **Dashboards** → **New** → **Import**
2. Upload `pv_monitoring.json` (or paste the JSON)
3. Select your **InfluxDB** datasource when prompted (or set dashboard variable **InfluxDB data source**)
4. Set dashboard variable **Inverter prefix (lowercase)** to your Modbus Manager prefix in **lowercase**, no underscore:
   - Home Assistant `{PREFIX}` = `SG` → Grafana `prefix` = `sg`
   - Entity `sensor.sg_total_dc_power` → Influx `"entity_id"='sg_total_dc_power'`
5. Set **Strompreis** / **Einspeisevergütung** (EUR/kWh) for the savings and year-comparison EUR panels
6. **Jahre zum Vergleich**: which calendar years to show in the monthly/yearly bar charts

Do **not** search-replace `{PREFIX}` inside this JSON. Use the Grafana `prefix` variable so one import works for `sg`, `sh10`, etc.

## What is parameterized

All Modbus Manager inverter/hybrid entities use `${prefix}_…`, including:

- Power: `total_dc_power`, `load_power`, `export_power`, `import_power`, `battery_power`, meter phases
- Energy: `total_pv_generation`, `daily_pv_generation`, `daily_consumed_energy`, import/export, battery charge/discharge
- Analysis: `autarky_rate_today` (stat **Autarkiegrad des Tages**)

## Optional panels (not Modbus Manager)

Two forecast queries are **unchanged** and are not prefix-based:

- `energy_production_today_remaining`
- `power_production_now_3`

They typically come from a PV-forecast integration. Hide or edit those panels if you do not have those entities in Influx.

## Year comparison

The **Jahresvergleich** row sits below **Ersparnis- und Einnahmenrechner**. Monthly/yearly bars use calendar windows on the **lifetime** counters (`total_pv_generation`, `total_exported_energy`), not the daily sensors. Those panels override the dashboard time range (`now-8y`) so a short Grafana picker (last 24h) does not empty 2024/2025.

If monthly bars are empty: confirm `prefix`, confirm Influx has `kWh` / `${prefix}_total_pv_generation`, then re-import after changing the JSON.

## Notes

- Calculated Home Assistant sensors (`autarky_rate_today`, signed battery power, …) only appear in Grafana if the Influx integration **includes** them.
- Connection type **RS485 vs WiNet-S** can change which SHx registers exist (see SHx template docs); hide unavailable panels.
- This file is an **example**, not a HACS asset. Copy it into Grafana; it is not loaded by the integration.
