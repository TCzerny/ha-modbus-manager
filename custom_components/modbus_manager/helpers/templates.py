"""Template helper functions for Modbus Manager."""
from typing import Any, Dict, Optional
from homeassistant.const import (
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_VOLTAGE,
    DEVICE_CLASS_TEMPERATURE,
)

def create_template_sensor(
    name: str,
    unique_id: str,
    value_template: str,
    unit: Optional[str] = None,
    device_class: Optional[str] = None,
    state_class: Optional[str] = None,
    icon: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create a template sensor configuration."""
    sensor = {
        "name": name,
        "unique_id": unique_id,
        "state": value_template,
    }
    
    if unit:
        sensor["unit_of_measurement"] = unit
    if device_class:
        sensor["device_class"] = device_class
    if state_class:
        sensor["state_class"] = state_class
    if icon:
        sensor["icon"] = icon
    if attributes:
        sensor["attributes"] = attributes
        
    return sensor

def create_power_sensor(
    name: str,
    unique_id: str,
    value_template: str,
    state_class: str = "measurement"
) -> Dict[str, Any]:
    """Create a power sensor template."""
    return create_template_sensor(
        name=name,
        unique_id=unique_id,
        value_template=value_template,
        unit="W",
        device_class=DEVICE_CLASS_POWER,
        state_class=state_class
    )

def create_energy_sensor(
    name: str,
    unique_id: str,
    value_template: str,
    state_class: str = "total_increasing"
) -> Dict[str, Any]:
    """Create an energy sensor template."""
    return create_template_sensor(
        name=name,
        unique_id=unique_id,
        value_template=value_template,
        unit="kWh",
        device_class=DEVICE_CLASS_ENERGY,
        state_class=state_class
    )

def calculate_daily_energy(sensor_value):
    """Berechnet den täglichen PV-Ertrag."""
    return sensor_value * 1.0

def calculate_weekly_energy(sensor_value):
    """Berechnet den wöchentlichen PV-Ertrag."""
    return sensor_value * 1.0

# Weitere Berechnungsfunktionen 