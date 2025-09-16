class ModbusManagerPanel extends HTMLElement {
  constructor() {
    super();
    this._lastRenderTime = 0;
  }

  set hass(hass) {
    this._hass = hass;
    // Throttle rendering to prevent endless loops
    const now = Date.now();
    if (now - this._lastRenderTime > 1000) { // Render max once per second
      this._lastRenderTime = now;
      this.render();
    }
  }

  render() {
    if (!this._hass) return;

    // Define global functions before rendering
    window.changeEmsMode = (mode) => {
      alert('EMS Mode changed to: ' + mode);
    };

    window.toggleSwitch = (entityId) => {
      alert('Toggle switch: ' + entityId);
    };

    const s = id => this._hass.states[id]?.state;
    const f = (v, d = 0) => (isNaN(parseFloat(v)) ? d : parseFloat(v));

    // Performance-Optimierung: Einmalige Durchsuchung aller States
    const allStates = this._hass.states;
    const sensorStates = {};

    // Einmalige Iteration über alle States
    for (const [id, state] of Object.entries(allStates)) {
      if (!id.startsWith("sensor.")) continue;
      sensorStates[id] = state;
    }

    // 1. TOTAL Inverter Information - Only show aggregated totals
    let html = `<div class="inverter-section">
      <h2>Inverter Information</h2>`;

    // Find PV Inverters from Modbus Manager integration
    const inverterEntities = [];
    const modbusEntities = [];

    // Find entities by checking their group attribute
    for (const [id, state] of Object.entries(allStates)) {
      const attributes = state.attributes || {};

      // Check if entity has a group attribute (indicates it's from modbus_manager)
      if (attributes.group) {
        modbusEntities.push(id);

        // Check if it's an inverter by group or power-related entities
        if (attributes.group.includes("PV") ||
            attributes.group.includes("inverter") ||
            (id.includes("_power") && !id.includes("_reactive_power") && !id.includes("_backup_power"))) {
          inverterEntities.push(id);
        }
      }
    }


    // Calculate total power using GROUP-based filtering
    const powerEntities = inverterEntities.filter(id => {
      const state = allStates[id];
      const attributes = state?.attributes || {};
      const hasCorrectGroup = (attributes.group === "PV_total_dc_power" ||
                              attributes.group === "PV_device_count");
      const hasCorrectName = (id.includes("total_dc_power") || id.includes("dc_power"));


      return hasCorrectGroup && hasCorrectName;
    });

    const totalPower = powerEntities.reduce((sum, entityId) => {
      const power = f(s(entityId));
      return sum + (isNaN(power) ? 0 : power);
    }, 0);

    // Calculate efficiency using GROUP-based filtering
    const efficiencyEntities = inverterEntities.filter(id => {
      const state = allStates[id];
      const attributes = state?.attributes || {};
      return (attributes.group === "PV_efficiency" ||
              attributes.group === "PV_device_count") && id.includes("_efficiency");
    });
    const totalEfficiency = efficiencyEntities.length > 0 ?
      efficiencyEntities.reduce((sum, id) => sum + f(s(id), 0), 0) / efficiencyEntities.length : 0;

    // Calculate average temperature using GROUP-based filtering
    const inverterTempEntities = inverterEntities.filter(id => {
      const state = allStates[id];
      const attributes = state?.attributes || {};
      return (attributes.group === "PV_temperature" ||
              attributes.group === "PV_device_count") &&
             (id.includes("inverter_temperature") || id.includes("dc_temperature") || id.includes("ac_temperature")) &&
             !id.includes("battery_temperature");
    });
    const totalTemperature = inverterTempEntities.length > 0 ?
      inverterTempEntities.reduce((sum, id) => sum + f(s(id), 0), 0) / inverterTempEntities.length : 0;

    // Calculate total daily energy using GROUP-based filtering
    const dailyEnergyEntities = inverterEntities.filter(id => {
      const state = allStates[id];
      const attributes = state?.attributes || {};
      const hasCorrectGroup = (attributes.group === "PV_daily_energy" ||
                              attributes.group === "PV_device_count");
      const hasCorrectName = (id.includes("daily_pv_generation") || id.includes("_daily_energy") || id.includes("daily_exported_energy"));


      return hasCorrectGroup && hasCorrectName;
    });
    const totalDailyEnergy = dailyEnergyEntities.reduce((sum, id) => sum + f(s(id), 0), 0);

    // Calculate total energy using GROUP-based filtering
    const totalEnergyEntities = inverterEntities.filter(id => {
      const state = allStates[id];
      const attributes = state?.attributes || {};
      return (attributes.group === "PV_total_energy" ||
              attributes.group === "PV_device_count") &&
             (id.includes("_total_energy") || id.includes("total_exported_energy"));
    });
    const totalEnergy = totalEnergyEntities.reduce((sum, id) => sum + f(s(id), 0), 0);

    // Additional useful metrics using GROUP-based filtering
    // Find house load power using GROUP-based filtering
    const loadPowerEntities = inverterEntities.filter(id => {
      const state = allStates[id];
      const attributes = state?.attributes || {};
      return (attributes.group === "PV_load_power" ||
              attributes.group === "PV_device_count") && id.includes("load_power");
    });
    const houseLoad = loadPowerEntities.length > 0 ?
      loadPowerEntities.reduce((sum, id) => sum + f(s(id), 0), 0) : 0;

    // Battery metrics using GROUP-based filtering
    const batterySOCEntities = inverterEntities.filter(id => {
      const state = allStates[id];
      const attributes = state?.attributes || {};
      return (attributes.group === "SBR_battery" ||
              attributes.group === "PV_device_count") &&
             (id.includes("battery_level") || id.includes("battery_soc") || id.includes("battery_state_of_charge"));
    });
    const batterySOC = batterySOCEntities.length > 0 ?
      batterySOCEntities.reduce((sum, id) => sum + f(s(id), 0), 0) / batterySOCEntities.length : 0;

    // Battery power using GROUP-based filtering
    const batteryPowerEntities = inverterEntities.filter(id => {
      const state = allStates[id];
      const attributes = state?.attributes || {};
      return (attributes.group === "SBR_battery" ||
              attributes.group === "PV_device_count") &&
             id.includes("battery_power") &&
             !id.includes("charging") &&
             !id.includes("discharging");
    });
    const batteryPower = batteryPowerEntities.length > 0 ?
      batteryPowerEntities.reduce((sum, id) => sum + f(s(id), 0), 0) : 0;

    // Separate charge and discharge
    const batteryCharge = batteryPower > 0 ? batteryPower : 0;
    const batteryDischarge = batteryPower < 0 ? Math.abs(batteryPower) : 0;

    html += `
      <div class="inverter-card">
          <div class="card-header">
          <h3>TOTAL Inverter</h3>
          <div class="status-indicator ${totalPower > 0 ? 'active' : 'inactive'}"></div>
        </div>
        <div class="inverter-metrics">
          <div class="metric-large">
            <div class="metric-icon">⚡</div>
            <div class="metric-content">
              <span class="metric-label">Total DC Power</span>
              <span class="metric-value">${totalPower.toFixed(0)} W</span>
            </div>
          </div>
          <div class="metric-large">
            <div class="metric-icon">📊</div>
            <div class="metric-content">
              <span class="metric-label">Average Efficiency</span>
              <span class="metric-value">${totalEfficiency.toFixed(1)}%</span>
            </div>
          </div>
          <div class="metric-large">
            <div class="metric-icon">🌡️</div>
            <div class="metric-content">
              <span class="metric-label">Average Temperature</span>
              <span class="metric-value">${totalTemperature.toFixed(1)}°C</span>
            </div>
          </div>
          <div class="metric-large">
            <div class="metric-icon">📈</div>
            <div class="metric-content">
              <span class="metric-label">Daily Energy</span>
              <span class="metric-value">${totalDailyEnergy.toFixed(1)} kWh</span>
              <span class="metric-description">Heute erzeugt</span>
            </div>
          </div>
        </div>
        <div class="energy-stats">
          <div class="energy-item">
            <span class="energy-label">Total Energy</span>
            <span class="energy-value">${totalEnergy.toFixed(1)} kWh</span>
            <span class="energy-description">Gesamt erzeugt</span>
          </div>
          <div class="energy-item">
            <span class="energy-label">House Load</span>
            <span class="energy-value">${houseLoad.toFixed(0)} W</span>
          </div>
          <div class="energy-item">
            <span class="energy-label">Battery SOC</span>
            <span class="energy-value">${batterySOC.toFixed(1)}%</span>
          </div>
          <div class="energy-item">
            <span class="energy-label">Battery Power</span>
            <span class="energy-value ${batteryPower >= 0 ? 'positive' : 'negative'}">${batteryPower.toFixed(0)} W</span>
          </div>
          <div class="energy-item">
            <span class="energy-label">Charge</span>
            <span class="energy-value">${batteryCharge.toFixed(0)} W</span>
          </div>
          <div class="energy-item">
            <span class="energy-label">Discharge</span>
            <span class="energy-value">${batteryDischarge.toFixed(0)} W</span>
          </div>
        </div>
      </div>`;

    html += `</div>`;

    // 2. EMS Settings with Controls
    const emsEnabled = s("switch.ems_enable") === "on";
    const emsMode = s("select.ems_mode") || "auto";
    const pvExcess = f(s("sensor.pv_excess_power"), 0);
    const batterySoc = f(s("sensor.sg_battery_soc"), null);
    const gridPrice = f(s("sensor.grid_price"), null);
    const isDayTime = s("binary_sensor.is_daytime") === "on";

    html += `
      <div class="ems-section">
        <h2>EMS Settings</h2>
        <div class="ems-controls">
          <div class="control-group">
            <label>EMS Enable/Disable:</label>
            <button class="toggle-btn ${emsEnabled ? 'active' : ''}"
                    onclick="toggleSwitch('switch.ems_enable')">
              ${emsEnabled ? 'ON' : 'OFF'}
            </button>
          </div>
          <div class="control-group">
            <label>Method:</label>
            <select class="method-select" onchange="changeEmsMode(this.value)">
              <option value="auto" ${emsMode === 'auto' ? 'selected' : ''}>Auto (Überschuss)</option>
              <option value="off" ${emsMode === 'off' ? 'selected' : ''}>Off</option>
              <option value="forced" ${emsMode === 'forced' ? 'selected' : ''}>Forced</option>
              <option value="manual" ${emsMode === 'manual' ? 'selected' : ''}>Manual</option>
            </select>
          </div>
        </div>
        <div class="ems-status">
          <div class="metric">
            <span class="label">PV Excess</span>
            <span class="value">${pvExcess.toFixed(0)} W</span>
          </div>
          <div class="metric">
            <span class="label">Battery SOC</span>
            <span class="value">${batterySoc ? batterySoc.toFixed(1) + '%' : 'N/A'}</span>
          </div>
          <div class="metric">
            <span class="label">Grid Price</span>
            <span class="value">${gridPrice ? gridPrice.toFixed(3) + ' €/kWh' : 'N/A'}</span>
          </div>
          <div class="metric">
            <span class="label">Day Time</span>
            <span class="value">${isDayTime ? 'Yes' : 'No'}</span>
        </div>
      </div>
      </div>`;

    // 3. Controllable Devices List
    html += `
      <div class="devices-section">
        <h2>Steuerbare Geräte</h2>`;

    // Find controllable devices (EV chargers, heat pumps, etc.)
    const controllableDevices = [];

    // Look for EV chargers by searching through all Modbus Manager devices
    let evChargerDevices = [];

    // Search through all Modbus Manager entries
    Object.keys(allStates).forEach(entityId => {
      const state = allStates[entityId];

      // Look for Modbus Manager config entries
      if (entityId.startsWith('sensor.modbus_manager_') && state.attributes) {
        const attributes = state.attributes;
        // Check if this is a device entry with EV charger type
        if (attributes.device_type === 'ev_charger' ||
            attributes.template === 'compleo_ebox_professional' ||
            attributes.template === 'compleo_ebox' ||
            entityId.includes('ebox')) {

          // Extract prefix from entity ID or attributes
          const prefix = attributes.prefix ||
                       entityId.replace('sensor.modbus_manager_', '').split('_')[0] ||
                       'ebox';

          // Check if EMS is enabled
          const emsEnabled = attributes.ems_config?.enabled ||
                           attributes.ems_enabled ||
                           false;

          if (emsEnabled) {
            evChargerDevices.push({
              prefix: prefix,
              name: attributes.name || `${attributes.template || 'EV Charger'} (${prefix})`,
              template: attributes.template || 'unknown',
              device_type: attributes.device_type || 'ev_charger',
              ems_config: attributes.ems_config || {
                enabled: true,
                power_calculation: {
                  phases: 3,
                  voltage_per_phase: 230,
                  min_current_per_phase: 0,
                  max_current_per_phase: 16
                }
              }
            });
          }
        }
      }
    });

    // Also search for entities with common EV charger prefixes
    const commonEvPrefixes = ['ebox', 'wallbox', 'ev_charger', 'compleo'];
    commonEvPrefixes.forEach(prefix => {
      const hasEvEntities = Object.keys(allStates).some(id =>
        id.includes(`${prefix}_`) && (id.includes("_power") || id.includes("_current") || id.includes("_voltage"))
      );

      if (hasEvEntities && !evChargerDevices.find(d => d.prefix === prefix)) {
        evChargerDevices.push({
          prefix: prefix,
          name: `EV Charger (${prefix})`,
          template: 'unknown',
          device_type: 'ev_charger',
          ems_config: {
            enabled: true,
            power_calculation: {
              phases: 3,
              voltage_per_phase: 230,
              min_current_per_phase: 0,
              max_current_per_phase: 16
            }
          }
        });
      }
    });


    // Check for eBox connection issues
    const eboxUnavailableEntities = Object.keys(allStates).filter(id =>
      id.includes("ebox_") && this._hass.states[id]?.state === "unavailable"
    );

    if (eboxUnavailableEntities.length > 0) {
      html += `<div class="error-section">
        <h3>⚠️ eBox Verbindungsprobleme</h3>
        <p><strong>${eboxUnavailableEntities.length}</strong> eBox-Sensoren sind nicht verfügbar:</p>
        <ul>
          ${eboxUnavailableEntities.slice(0, 5).map(id => `<li>${id}</li>`).join('')}
          ${eboxUnavailableEntities.length > 5 ? `<li>... und ${eboxUnavailableEntities.length - 5} weitere</li>` : ''}
        </ul>
        <p><strong>Mögliche Ursachen:</strong></p>
        <ul>
          <li>eBox ist nicht eingeschaltet oder nicht am Netzwerk</li>
          <li>Falsche Modbus-Konfiguration (IP, Port, Slave-ID)</li>
          <li>Netzwerkprobleme</li>
          <li>eBox unterstützt nicht alle Register aus dem Template</li>
        </ul>
      </div>`;
    }

    // Process each EV charger device
    evChargerDevices.forEach(device => {
      const prefix = device.prefix || 'unknown';
      const deviceName = device.name || `${device.template} (${prefix})`;

      // Get entities for this specific device
      const deviceEntities = Object.keys(allStates).filter(id =>
        id.includes(`${prefix}_`) && (id.includes("_power") || id.includes("_current") || id.includes("_voltage"))
      );

      if (deviceEntities.length > 0) {
        // Only sum actual power values for this device
        const evPowerEntities = deviceEntities.filter(id =>
          id.includes("_power") &&
          !id.includes("_reactive_power") &&
          !id.includes("_apparent_power")
        );

        const evPower = evPowerEntities.reduce((sum, entityId) => {
          const power = f(s(entityId));
          return sum + (isNaN(power) ? 0 : power);
        }, 0);

        const evStatus = s(`sensor.${prefix}_charging_status`) || "unknown";
        const evCurrent = f(s(`sensor.${prefix}_total_current`), 0);

        // Get EMS config from template if available
        let phases = 3;
        let voltagePerPhase = 230;
        let minCurrent = 0;  // Disabled
        let maxCurrent = 16;

        // Use config from template if available
        if (device.ems_config && device.ems_config.power_calculation) {
          phases = device.ems_config.power_calculation.phases || 3;
          voltagePerPhase = device.ems_config.power_calculation.voltage_per_phase || 230;
          minCurrent = device.ems_config.power_calculation.min_current_per_phase || 0;
          maxCurrent = device.ems_config.power_calculation.max_current_per_phase || 16;
        }

        // Calculate power limits dynamically
        const minPower = phases * minCurrent * voltagePerPhase;  // 0 W (disabled)
        const maxPower = phases * maxCurrent * voltagePerPhase;  // 11040 W (3 * 16 * 230)

        const emsConfig = {
          min_current: minCurrent,
          max_current: maxCurrent,
          phases: phases,
          voltage_per_phase: voltagePerPhase,
          min_power: minPower,
          max_power: maxPower,
          control_entities: device.ems_config ? device.ems_config.control_entities : null,
          device_prefix: prefix
        };

        controllableDevices.push({
          name: deviceName,
          type: "ev_charger",
          icon: "🚗",
          currentPower: evPower,
          status: evStatus,
          current: evCurrent,
          controllable: true,
          emsConfig: emsConfig
        });
      }
    });

    // Look for heat pumps (example patterns)
    const heatPumpEntities = Object.keys(allStates).filter(id =>
      id.includes("heat_pump") || id.includes("klimaanlage") || id.includes("wärmepumpe")
    );

    if (heatPumpEntities.length > 0) {
      heatPumpEntities.forEach(entityId => {
        const power = f(s(entityId));
        controllableDevices.push({
          name: "Wärmepumpe",
          type: "heat_pump",
          icon: "❄️",
          currentPower: power,
          status: s(entityId),
          controllable: true
        });
      });
    }

    // Look for water heaters
    const waterHeaterEntities = Object.keys(allStates).filter(id =>
      id.includes("water_heater") || id.includes("boiler") || id.includes("speicher")
    );

    if (waterHeaterEntities.length > 0) {
      waterHeaterEntities.forEach(entityId => {
        const power = f(s(entityId));
        controllableDevices.push({
          name: "Warmwasser",
          type: "water_heater",
          icon: "🔥",
          currentPower: power,
          status: s(entityId),
          controllable: true
        });
      });
    }

    // Look for pool heating
    const poolHeatingEntities = Object.keys(allStates).filter(id =>
      id.includes("pool") || id.includes("schwimmbad")
    );

    if (poolHeatingEntities.length > 0) {
      poolHeatingEntities.forEach(entityId => {
        const power = f(s(entityId));
        controllableDevices.push({
          name: "Pool Heizung",
          type: "pool_heating",
          icon: "🏊",
          currentPower: power,
          status: s(entityId),
          controllable: true
        });
      });
    }

    // Display controllable devices
    if (controllableDevices.length === 0) {
      html += `
        <div class="no-devices">
          <h3>Keine steuerbaren Geräte gefunden</h3>
          <p>Steuerbare Geräte werden automatisch erkannt:</p>
          <ul>
            <li>🚗 Wallbox (eBox)</li>
            <li>❄️ Wärmepumpe/Klimaanlage</li>
            <li>🔥 Warmwasser-Speicher</li>
            <li>🏊 Pool-Heizung</li>
          </ul>
        </div>`;
    } else {
      controllableDevices.forEach(device => {
        html += `
          <div class="controllable-device-card">
            <div class="device-header">
              <div class="device-icon">${device.icon}</div>
              <div class="device-info">
                <h4>${device.name}</h4>
                <span class="device-type">${device.type.replace("_", " ").toUpperCase()}</span>
              </div>
              <div class="device-status ${device.currentPower > 0 ? 'active' : 'inactive'}">
                ${device.currentPower > 0 ? 'Aktiv' : 'Inaktiv'}
              </div>
            </div>
            <div class="device-metrics">
              <div class="metric">
                <span class="label">Leistung</span>
                <span class="value">${device.currentPower.toFixed(0)} W</span>
              </div>
              <div class="metric">
                <span class="label">Status</span>
                <span class="value">${device.status}</span>
              </div>
              ${device.current ? `
                <div class="metric">
                  <span class="label">Strom</span>
                  <span class="value">${device.current.toFixed(1)} A</span>
                </div>
              ` : ''}
            </div>
            <div class="device-controls">
              <button class="control-btn" onclick="alert('Toggle: ${device.name}')">
                ${device.currentPower > 0 ? 'Ausschalten' : 'Einschalten'}
              </button>
              <button class="control-btn secondary" onclick="alert('Power Limit: ${device.name}')">
                Leistung begrenzen
              </button>
            </div>
            ${device.emsConfig ? `
              <div class="ems-info">
                <h5>EMS Konfiguration:</h5>
                <div class="ems-details">
                  <span>Min: ${device.emsConfig.min_power} W (${device.emsConfig.min_current} A)</span>
                  <span>Max: ${device.emsConfig.max_power} W (${device.emsConfig.max_current} A)</span>
                  <span>Phasen: ${device.emsConfig.phases}</span>
                </div>
              </div>
            ` : ''}
          </div>`;
      });
    }

    html += `</div>`;

    html += `</div>`;

    this.innerHTML = html + `
      <style>
      .container {
          padding: 20px;
        max-width: 1200px;
        margin: 0 auto;
      }

        h2 {
          color: #03a9f4;
          border-bottom: 2px solid #03a9f4;
          padding-bottom: 10px;
          margin-bottom: 20px;
        }

        h3 {
          color: #1976d2;
          margin-bottom: 15px;
        }

        h4 {
          color: #424242;
          margin-bottom: 10px;
        }

        .inverter-section, .ems-section, .devices-section {
          margin-bottom: 30px;
          background: #f5f5f5;
          padding: 20px;
          border-radius: 8px;
        }

        .inverter-card {
          background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
          padding: 20px;
          margin-bottom: 20px;
          border-radius: 12px;
          box-shadow: 0 4px 12px rgba(0,0,0,0.1);
          border: 1px solid #e9ecef;
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .inverter-card:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 20px rgba(0,0,0,0.15);
        }

        .card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
          padding-bottom: 15px;
          border-bottom: 2px solid #e9ecef;
        }

        .status-indicator {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          margin-left: 10px;
        }

        .status-indicator.active {
          background-color: #4caf50;
          box-shadow: 0 0 8px rgba(76, 175, 80, 0.5);
        }

        .status-indicator.inactive {
          background-color: #9e9e9e;
        }

        .inverter-metrics {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 20px;
          margin-bottom: 20px;
        }

        .metric-large {
          display: flex;
          align-items: center;
          padding: 15px;
          background: white;
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.05);
          border-left: 4px solid #03a9f4;
        }

        .metric-icon {
          font-size: 24px;
          margin-right: 15px;
          opacity: 0.8;
        }

        .metric-content {
          display: flex;
          flex-direction: column;
        }

        .metric-label {
          font-size: 12px;
          color: #666;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 4px;
        }

        .metric-value {
          font-size: 18px;
          font-weight: 600;
          color: #333;
        }

        .energy-stats {
          display: flex;
          justify-content: space-around;
          padding: 15px;
          background: rgba(3, 169, 244, 0.05);
          border-radius: 8px;
          border: 1px solid rgba(3, 169, 244, 0.1);
        }

        .energy-item {
          text-align: center;
        }

        .energy-label {
          display: block;
          font-size: 12px;
          color: #666;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 5px;
        }

        .energy-value {
          display: block;
          font-size: 16px;
          font-weight: 600;
          color: #03a9f4;
        }

        .controllable-device-card {
          background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
          padding: 20px;
          margin-bottom: 20px;
          border-radius: 12px;
          box-shadow: 0 4px 12px rgba(0,0,0,0.1);
          border: 1px solid #e9ecef;
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .controllable-device-card:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 20px rgba(0,0,0,0.15);
        }

        .device-header {
          display: flex;
          align-items: center;
          margin-bottom: 15px;
          padding-bottom: 15px;
          border-bottom: 2px solid #e9ecef;
        }

        .device-icon {
          font-size: 32px;
          margin-right: 15px;
        }

        .device-info h4 {
          margin: 0 0 5px 0;
          color: #333;
        }

        .device-type {
          font-size: 12px;
          color: #666;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .metric-description {
          font-size: 0.7em;
          color: #888;
          margin-top: 2px;
          display: block;
        }

        .device-status {
          margin-left: auto;
          padding: 5px 12px;
          border-radius: 20px;
          font-size: 12px;
          font-weight: 600;
          text-transform: uppercase;
        }

        .device-status.active {
          background: #4caf50;
          color: white;
        }

        .device-status.inactive {
          background: #e0e0e0;
          color: #666;
        }

        .device-metrics {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 15px;
          margin-bottom: 20px;
        }

        .device-controls {
          display: flex;
          gap: 10px;
        }

        .control-btn {
          padding: 10px 20px;
          border: none;
          border-radius: 6px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s ease;
          background: #03a9f4;
          color: white;
        }

        .control-btn.secondary {
          background: #e0e0e0;
          color: #666;
        }

        .control-btn:hover {
          transform: translateY(-1px);
          box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }

        .ems-info {
          margin-top: 15px;
          padding: 15px;
          background: rgba(3, 169, 244, 0.05);
          border-radius: 6px;
          border: 1px solid rgba(3, 169, 244, 0.1);
        }

        .ems-info h5 {
          margin: 0 0 10px 0;
          color: #03a9f4;
          font-size: 14px;
        }

        .ems-details {
          display: flex;
          flex-wrap: wrap;
          gap: 15px;
        }

        .ems-details span {
          font-size: 12px;
          color: #666;
          background: white;
          padding: 5px 10px;
          border-radius: 4px;
          border: 1px solid #e0e0e0;
        }

        .device-card {
          background: white;
          padding: 15px;
          margin-bottom: 15px;
          border-radius: 6px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .device-info {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 15px;
        }

        .metric {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px 12px;
          background: #f8f9fa;
          border-radius: 4px;
        }

        .metric .label {
          font-weight: 500;
          color: #666;
        }

        .metric .value {
          font-weight: 600;
          color: #333;
        }

        .metric .value.positive {
          color: #4caf50;
        }

        .metric .value.negative {
          color: #f44336;
        }

        .ems-controls {
          display: flex;
          gap: 30px;
          margin-bottom: 20px;
          padding: 20px;
          background: white;
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }

        .control-group {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .control-group label {
          font-weight: 600;
          color: #333;
          font-size: 14px;
        }

        .toggle-btn {
          padding: 10px 20px;
          border: none;
          border-radius: 6px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s ease;
          background: #e0e0e0;
          color: #666;
        }

        .toggle-btn.active {
          background: #4caf50;
          color: white;
        }

        .toggle-btn:hover {
          transform: translateY(-1px);
          box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }

        .method-select {
          padding: 10px 15px;
          border: 2px solid #e0e0e0;
          border-radius: 6px;
          font-size: 14px;
          background: white;
          cursor: pointer;
          transition: border-color 0.2s ease;
        }

        .method-select:focus {
          outline: none;
          border-color: #03a9f4;
        }

        .ems-status {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 15px;
        }

        .device-type-section {
          margin-bottom: 20px;
        }

        .no-devices {
          text-align: center;
          padding: 40px;
          background: white;
          border-radius: 6px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .no-devices ul {
          text-align: left;
          display: inline-block;
        }

        .no-devices li {
          margin-bottom: 5px;
        }

        .status-info {
          background: #f0f8ff;
          border: 1px solid #03a9f4;
          border-radius: 6px;
          padding: 15px;
          margin-bottom: 20px;
        }

        .error-section {
          background: #fff3cd;
          border: 1px solid #ffc107;
          border-radius: 6px;
          padding: 15px;
          margin-bottom: 20px;
        }

        .error-section h3 {
          color: #856404;
          margin-top: 0;
        }

        .error-section ul {
          margin: 10px 0;
        }

        .error-section li {
          margin-bottom: 5px;
        }
      </style>
    `;
  }
}

customElements.define('modbus-manager-panel', ModbusManagerPanel);
