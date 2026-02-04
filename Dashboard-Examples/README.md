# Dashboard Examples

This folder contains example dashboard configurations for the Modbus Manager integration.

## Screenshot Examples

### Battery Dashboards

![Battery Overview](BatteryOverview.png)
![Balancing Analytics](BalancingAnalytics.png)
![Module Details](ModuleDetails.png)
![Advanced Metrics](AdvancedMetrics.png)

### PV Dashboards

![PV Overview](PVOverview.png)
![MPPT Analysis](MPPTAnalysis.png)
![Energy Flow Analysis](EnergyFlowAnalysis.png)
![Statistics](Statistics.png)

## Dashboard Files

### Battery Dashboards

#### sungrow_sbr_battery_analysis_standard.yaml
Standard Home Assistant cards version with new Sections layout. Uses only built-in HA cards.

#### sungrow_sbr_battery_analysis_mushroom.yaml
Mushroom Cards version with new Sections layout. Requires Mushroom Cards (HACS).

#### sungrow_sbr_battery_analysis_simple.yaml
Simplified version using only built-in Home Assistant cards. No custom cards required - works out of the box!

#### sungrow_sbr_battery_analysis.yaml
Legacy version with custom cards (Mushroom Cards and ApexCharts Card) for a modern, visually appealing interface.

### PV Dashboards

#### sungrow_pv_analysis_standard.yaml
Standard Home Assistant cards version with new Sections layout. Uses only built-in HA cards for PV monitoring.

#### sungrow_pv_analysis_mushroom.yaml
Mushroom Cards version with new Sections layout. Requires Mushroom Cards (HACS).

#### sungrow_pv_analysis_simple.yaml
Simplified version using only built-in Home Assistant cards. No custom cards required - works out of the box!

## Sungrow SBR Battery Analysis Dashboard

Both dashboard files provide comprehensive monitoring and analysis for Sungrow SBR battery systems.

### Features

- **Battery Overview**: Main status indicators (SoC, Voltage, Current, Temperature, SoH)
- **Balancing Analysis**: Voltage spread, module deviations, and imbalance metrics
- **Module Details**: Cell voltage ranges and comparisons per module
- **Advanced Metrics**: Historical data and detailed balancing metrics

### Installation

1. Copy the dashboard YAML file to your Home Assistant configuration directory
2. **Important**: Replace all instances of `{PREFIX}` with your actual device prefix (e.g., `SBR`)
   - Example: `sensor.{PREFIX}_battery_1_voltage` → `sensor.SBR_battery_1_voltage`
3. Import the dashboard in Home Assistant:
   - Go to **Settings** → **Dashboards** → **+ New Dashboard**
   - Choose **Import from YAML**
   - Paste the content of the YAML file (after replacing `{PREFIX}`)

### Required Custom Cards (Full Version Only)

The `sungrow_sbr_battery_analysis.yaml` dashboard uses the following custom cards (install via HACS if not already installed):

- **Mushroom Cards** (`custom:mushroom-entity-card`)
  - HACS Repository: `https://github.com/piitaya/lovelace-mushroom`

- **ApexCharts Card** (`custom:apexcharts-card`)
  - HACS Repository: `https://github.com/RomRider/apexcharts-card`

**Note**: The `sungrow_sbr_battery_analysis_simple.yaml` version uses only built-in Home Assistant cards and requires no additional installations.

### Dashboard Structure

The dashboard is organized into 4 views:

1. **Battery Overview** (`/overview`)
   - Main battery status cards
   - Energy statistics

2. **Balancing Analysis** (`/balancing`)
   - Voltage spread and deviation metrics
   - Module deviation charts and tables

3. **Module Details** (`/modules`)
   - Cell voltage ranges per module
   - Max/min cell voltage comparisons

4. **Advanced Metrics** (`/advanced`)
   - All balancing metrics in one view
   - Historical voltage spread chart
   - Cell voltage and temperature extremes

### Color Coding

The dashboard uses color coding to indicate status:

- **Green**: Normal/Good values
- **Orange**: Warning values
- **Red**: Critical values

Thresholds are configured in the card templates and can be adjusted based on your battery specifications.

### Customization

You can customize the dashboard by:

- Adjusting color thresholds in the `icon_color` sections
- Adding or removing entities from the cards
- Modifying chart types and configurations
- Changing the layout (grid columns, card sizes, etc.)

### Notes

- The dashboard assumes you have 8 modules configured. If you have fewer modules, some entities may show as "unavailable" - this is normal.
- All calculated entities use 5 decimal places precision for accurate balancing analysis.
- Historical charts require the entities to have history enabled in Home Assistant.

## Sungrow PV Analysis Dashboard

The PV dashboards provide comprehensive monitoring and analysis for Sungrow PV inverter systems.

### Features

- **PV Overview**: Main status indicators (Total DC Power, Daily/Total PV Generation, Inverter Temperature)
- **MPPT Analysis**: Individual MPPT tracker voltages, currents, and power analysis
- **AC Output**: Phase voltages, currents, and power for 3-phase systems
- **Statistics**: Long-term generation statistics and trends

### Installation

1. Copy the dashboard YAML file to your Home Assistant configuration directory
2. **Important**: Replace all instances of `{PREFIX}` with your actual device prefix (e.g., `SG`)
   - Example: `sensor.{PREFIX}_total_dc_power` → `sensor.SG_total_dc_power`
3. Import the dashboard in Home Assistant:
   - Go to **Settings** → **Dashboards** → **+ New Dashboard**
   - Choose **Import from YAML**
   - Paste the content of the YAML file (after replacing `{PREFIX}`)

### Required Custom Cards (Mushroom Version Only)

The `sungrow_pv_analysis_mushroom.yaml` dashboard uses:
- **Mushroom Cards** (`custom:mushroom-entity-card`)
  - HACS Repository: `https://github.com/piitaya/lovelace-mushroom`

**Note**: The `sungrow_pv_analysis_standard.yaml` and `sungrow_pv_analysis_simple.yaml` versions use only built-in Home Assistant cards and require no additional installations.

### Dashboard Structure

The PV dashboard is organized into 3 views:

1. **PV Overview** (`/overview`)
   - PV generation status cards
   - MPPT tracker information
   - AC output details
   - Historical generation charts

2. **MPPT Analysis** (`/mppt`)
   - MPPT voltage and current trends
   - Individual MPPT tracker details
   - Long-term MPPT statistics

3. **Statistics** (`/statistics`)
   - Daily and total PV generation statistics
   - Power distribution analysis
   - Inverter temperature trends

### Notes

- The dashboard supports up to 4 MPPT trackers. If you have fewer trackers, some entities may show as "unavailable" - this is normal.
- For single-phase systems, only Phase A entities will be populated.
- Historical charts require the entities to have history enabled in Home Assistant.

### Support

For issues or questions about the Modbus Manager integration, please refer to the main project documentation or open an issue on GitHub.
