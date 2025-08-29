# 🔧 Project Description: Home Assistant Modbus Manager

## 👤 Author: TCzerny  
## 📦 Repository: [github.com/TCzerny/ha-modbus-manager](https://github.com/TCzerny/ha-modbus-manager)  
## 📅 Status: August 2025  
## 🧠 Goal: A universal, template-driven Modbus integration for Home Assistant

---

## 🧱 Project Goal

The Modbus Manager aims to provide a modular, scalable and maintainable platform for managing Modbus devices in Home Assistant. The goal is to integrate any devices such as PV inverters, heat pumps, wallboxes, HVAC systems or heating systems through a unified template system — without manual YAML configuration or automations.

---

## 🔧 Architecture Overview

### 📁 Template Structure

Templates are located under `device_definitions/*.yaml` and contain:

- `registers:` → Modbus sensors  
- `calculated:` → Calculated sensors via Jinja2  
- `controls:` → Direct Modbus control (`number`, `select`, `button`)  
- `version:` → Template versioning for update detection  
- `type:` → Device type (e.g. `inverter`, `heatpump`, `wallbox`)  

### 🧩 Modules

| File                   | Function                                           |
|------------------------|----------------------------------------------------|
| `template_loader.py`   | Loads and validates templates                      |
| `entity_factory.py`    | Creates entities from template data                |
| `controls.py`          | Direct Modbus control                              |
| `calculated.py`        | Calculated sensors with Jinja2                    |
| `modbus_device.py`     | Central device class                               |
| `config_flow.py`       | UI setup for devices                               |

---

## ✅ Features

- Dynamic loading of templates
- Direct control without automations (`ModbusNumberEntity`, `ModbusSelectEntity`, `ModbusButtonEntity`)
- Calculated sensors with `{prefix}` placeholder
- Support for `data_type`, `length`, `bitmask`
- Semi-automatic template updates with version comparison
- Aggregation via `group:` field
- UI-compatible, no YAML needed

---

## 📋 Example Template: `heatpump_generic.yaml`

```yaml
name: Generic Heatpump
type: heatpump
version: 2
slave_id: 1

registers:
  - name: "Flow Temperature"
    address: 30010
    unit: "°C"
    scale: 0.1
    device_class: temperature
    state_class: measurement
    group: heat_flow

  - name: "Compressor Status"
    address: 30020
    data_type: bitfield
    bitmask: 0x01
    device_class: running
    group: heat_status

calculated:
  - name: "Delta Temperature"
    type: sensor
    template: "{{ states('sensor.{prefix}_flow_temperature') | float - states('sensor.{prefix}_return_temperature') | float }}"
    unit: "°C"
    device_class: temperature
    state_class: measurement
    group: heat_delta

controls:
  - type: number
    name: "Target Temperature"
    address: 40010
    scale: 0.1
    unit: "°C"
    min: 30
    max: 60
    step: 0.5
    group: heat_control

```
