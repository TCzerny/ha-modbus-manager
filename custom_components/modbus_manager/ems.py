"""Energy Management System (EMS) for Modbus Manager."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from homeassistant.components.number import NumberEntity
from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)


class EMSDevice:
    """Represents a device managed by the EMS system."""

    def __init__(
        self,
        device_id: str,
        name: str,
        priority: int,
        max_power: float,
        entity_id: str,
        auto_switch_entity: str,
        power_sensor_entity: str,
        device_type: str = "load",
    ):
        self.device_id = device_id
        self.name = name
        self.priority = priority
        self.max_power = max_power
        self.entity_id = entity_id
        self.auto_switch_entity = auto_switch_entity
        self.power_sensor_entity = power_sensor_entity
        self.device_type = device_type
        self.current_power = 0.0
        self.is_auto_enabled = False
        self.is_active = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert device to dictionary."""
        return {
            "device_id": self.device_id,
            "name": self.name,
            "priority": self.priority,
            "max_power": self.max_power,
            "entity_id": self.entity_id,
            "auto_switch_entity": self.auto_switch_entity,
            "power_sensor_entity": self.power_sensor_entity,
            "device_type": self.device_type,
            "current_power": self.current_power,
            "is_auto_enabled": self.is_auto_enabled,
            "is_active": self.is_active,
        }


class EMSPowerCalculator:
    """Calculates PV excess power and manages power allocation."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._pv_production_sensors = []
        self._load_sensors = []
        self._battery_sensors = []
        self._grid_sensors = []

    async def discover_sensors(self) -> None:
        """Discover relevant sensors for power calculation."""
        states = self.hass.states.async_all()

        for state in states:
            entity_id = state.entity_id
            if not entity_id.startswith("sensor."):
                continue

            # PV Production sensors
            if any(
                keyword in entity_id.lower()
                for keyword in ["pv", "solar", "mppt", "dc_power"]
            ):
                if "power" in entity_id.lower() and "total" in entity_id.lower():
                    self._pv_production_sensors.append(entity_id)

            # Load sensors
            elif any(
                keyword in entity_id.lower()
                for keyword in ["load", "consumption", "usage"]
            ):
                if "power" in entity_id.lower():
                    self._load_sensors.append(entity_id)

            # Battery sensors
            elif any(
                keyword in entity_id.lower() for keyword in ["battery", "storage"]
            ):
                if "power" in entity_id.lower():
                    self._battery_sensors.append(entity_id)

            # Grid sensors
            elif any(
                keyword in entity_id.lower() for keyword in ["grid", "meter", "net"]
            ):
                if "power" in entity_id.lower():
                    self._grid_sensors.append(entity_id)

        _LOGGER.debug(
            "EMS Power Calculator discovered: PV=%d, Load=%d, Battery=%d, Grid=%d",
            len(self._pv_production_sensors),
            len(self._load_sensors),
            len(self._battery_sensors),
            len(self._grid_sensors),
        )

    def calculate_pv_excess(self) -> float:
        """Calculate PV excess power."""
        try:
            # Calculate total PV production
            total_pv = 0.0
            for sensor_id in self._pv_production_sensors:
                state = self.hass.states.get(sensor_id)
                if state and state.state not in ["unknown", "unavailable"]:
                    try:
                        total_pv += float(state.state)
                    except (ValueError, TypeError):
                        continue

            # Calculate total load
            total_load = 0.0
            for sensor_id in self._load_sensors:
                state = self.hass.states.get(sensor_id)
                if state and state.state not in ["unknown", "unavailable"]:
                    try:
                        total_load += float(state.state)
                    except (ValueError, TypeError):
                        continue

            # Calculate battery power (positive = charging, negative = discharging)
            battery_power = 0.0
            for sensor_id in self._battery_sensors:
                state = self.hass.states.get(sensor_id)
                if state and state.state not in ["unknown", "unavailable"]:
                    try:
                        battery_power += float(state.state)
                    except (ValueError, TypeError):
                        continue

            # PV Excess = PV Production - Load - Battery Charging
            pv_excess = total_pv - total_load - max(0, battery_power)

            _LOGGER.debug(
                "PV Excess Calculation: PV=%.1fW, Load=%.1fW, Battery=%.1fW, Excess=%.1fW",
                total_pv,
                total_load,
                battery_power,
                pv_excess,
            )

            return max(0, pv_excess)  # Only positive excess

        except Exception as e:
            _LOGGER.error("Error calculating PV excess: %s", str(e))
            return 0.0


class EMSPriorityManager:
    """Manages device priorities and power allocation."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.devices: List[EMSDevice] = []

    def add_device(self, device: EMSDevice) -> None:
        """Add a device to the priority manager."""
        self.devices.append(device)
        self.devices.sort(key=lambda x: x.priority)
        _LOGGER.debug("Added device %s with priority %d", device.name, device.priority)

    def remove_device(self, device_id: str) -> None:
        """Remove a device from the priority manager."""
        self.devices = [d for d in self.devices if d.device_id != device_id]
        _LOGGER.debug("Removed device %s", device_id)

    def get_available_devices(self) -> List[EMSDevice]:
        """Get devices that are auto-enabled and available."""
        return [
            device
            for device in self.devices
            if device.is_auto_enabled and not device.is_active
        ]

    def allocate_power(self, available_power: float) -> Dict[str, float]:
        """Allocate power to devices based on priority."""
        allocation = {}
        remaining_power = available_power

        for device in self.get_available_devices():
            if remaining_power <= 0:
                break

            # Allocate power up to device's max power
            allocated_power = min(remaining_power, device.max_power)
            allocation[device.device_id] = allocated_power
            remaining_power -= allocated_power

            _LOGGER.debug(
                "Allocated %.1fW to %s (priority %d)",
                allocated_power,
                device.name,
                device.priority,
            )

        return allocation


class EMSSensor(SensorEntity, RestoreEntity):
    """EMS Status Sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        unique_id: str,
        device_info: DeviceInfo,
        ems_manager: "EMSManager",
    ):
        self.hass = hass
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        self._ems_manager = ems_manager
        self._attr_unit_of_measurement = "W"
        self._attr_device_class = "power"
        self._attr_state_class = "measurement"
        self._attr_icon = "mdi:lightning-bolt"

    @property
    def state(self) -> float:
        """Return the current PV excess power."""
        return self._ems_manager.power_calculator.calculate_pv_excess()

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes."""
        return {
            "ems_mode": self._ems_manager.mode,
            "active_devices": len(
                self._ems_manager.priority_manager.get_available_devices()
            ),
            "total_managed_power": sum(
                device.current_power
                for device in self._ems_manager.priority_manager.devices
            ),
            "devices": [
                device.to_dict()
                for device in self._ems_manager.priority_manager.devices
            ],
        }


class EMSSwitch(SwitchEntity, RestoreEntity):
    """EMS Enable Switch."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        unique_id: str,
        device_info: DeviceInfo,
        ems_manager: "EMSManager",
    ):
        self.hass = hass
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        self._ems_manager = ems_manager
        self._attr_icon = "mdi:power"
        self._attr_is_on = False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on EMS."""
        self._attr_is_on = True
        await self._ems_manager.enable()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off EMS."""
        self._attr_is_on = False
        await self._ems_manager.disable()
        self.async_write_ha_state()


class EMSModeSelect(SelectEntity, RestoreEntity):
    """EMS Mode Select."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        unique_id: str,
        device_info: DeviceInfo,
        ems_manager: "EMSManager",
    ):
        self.hass = hass
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        self._ems_manager = ems_manager
        self._attr_icon = "mdi:cog"
        self._attr_options = ["auto", "pv_priority", "battery_priority", "manual"]
        self._attr_current_option = "auto"

    async def async_select_option(self, option: str) -> None:
        """Select EMS mode."""
        self._attr_current_option = option
        await self._ems_manager.set_mode(option)
        self.async_write_ha_state()


class EMSManager:
    """Main EMS Manager class."""

    def __init__(self, hass: HomeAssistant, prefix: str = "ems"):
        self.hass = hass
        self.prefix = prefix
        self.mode = "auto"
        self.is_enabled = False

        # Initialize components
        self.power_calculator = EMSPowerCalculator(hass)
        self.priority_manager = EMSPriorityManager(hass)

        # EMS entities
        self.entities: List[SensorEntity] = []

        # Update interval
        self._update_interval = 30  # seconds
        self._update_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Initialize the EMS system."""
        try:
            # Discover sensors
            await self.power_calculator.discover_sensors()

            # Create EMS entities
            await self._create_entities()

            # Start update task
            self._update_task = asyncio.create_task(self._update_loop())

            _LOGGER.info("EMS Manager initialized successfully")

        except Exception as e:
            _LOGGER.error("Failed to initialize EMS Manager: %s", str(e))
            raise

    async def _create_entities(self) -> None:
        """Create EMS entities."""
        device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self.prefix}_ems")},
            name=f"{self.prefix.title()} Energy Management System",
            manufacturer="Modbus Manager",
            model="EMS Controller",
        )

        # PV Excess Sensor
        pv_excess_sensor = EMSSensor(
            hass=self.hass,
            name=f"{self.prefix.title()} PV Excess Power",
            unique_id=f"{self.prefix}_pv_excess_power",
            device_info=device_info,
            ems_manager=self,
        )
        self.entities.append(pv_excess_sensor)

        # EMS Enable Switch
        ems_switch = EMSSwitch(
            hass=self.hass,
            name=f"{self.prefix.title()} EMS Enable",
            unique_id=f"{self.prefix}_ems_enable",
            device_info=device_info,
            ems_manager=self,
        )
        self.entities.append(ems_switch)

        # EMS Mode Select
        ems_mode_select = EMSModeSelect(
            hass=self.hass,
            name=f"{self.prefix.title()} EMS Mode",
            unique_id=f"{self.prefix}_ems_mode",
            device_info=device_info,
            ems_manager=self,
        )
        self.entities.append(ems_mode_select)

    async def add_device(
        self,
        device_id: str,
        name: str,
        priority: int,
        max_power: float,
        entity_id: str,
        auto_switch_entity: str,
        power_sensor_entity: str,
        device_type: str = "load",
    ) -> None:
        """Add a device to EMS management."""
        device = EMSDevice(
            device_id=device_id,
            name=name,
            priority=priority,
            max_power=max_power,
            entity_id=entity_id,
            auto_switch_entity=auto_switch_entity,
            power_sensor_entity=power_sensor_entity,
            device_type=device_type,
        )

        self.priority_manager.add_device(device)
        _LOGGER.info("Added device %s to EMS management", name)

    async def enable(self) -> None:
        """Enable EMS."""
        self.is_enabled = True
        _LOGGER.info("EMS enabled")

    async def disable(self) -> None:
        """Disable EMS."""
        self.is_enabled = False
        # Turn off all managed devices
        for device in self.priority_manager.devices:
            if device.is_active:
                await self._turn_off_device(device)
        _LOGGER.info("EMS disabled")

    async def set_mode(self, mode: str) -> None:
        """Set EMS mode."""
        self.mode = mode
        _LOGGER.info("EMS mode set to %s", mode)

        # Apply mode-specific logic
        if mode == "battery_priority":
            # Turn off all devices to prioritize battery charging
            for device in self.priority_manager.devices:
                if device.is_active:
                    await self._turn_off_device(device)
        elif mode == "pv_priority":
            # Enable all devices to use PV excess
            for device in self.priority_manager.devices:
                if device.is_auto_enabled and not device.is_active:
                    await self._turn_on_device(device)

    async def _update_loop(self) -> None:
        """Main update loop."""
        while True:
            try:
                if self.is_enabled:
                    await self._update_devices()
                await asyncio.sleep(self._update_interval)
            except Exception as e:
                _LOGGER.error("Error in EMS update loop: %s", str(e))
                await asyncio.sleep(60)  # Wait longer on error

    async def _update_devices(self) -> None:
        """Update device states and manage power allocation."""
        try:
            # Update device states
            for device in self.priority_manager.devices:
                await self._update_device_state(device)

            # Calculate PV excess
            pv_excess = self.power_calculator.calculate_pv_excess()

            # Allocate power based on mode
            if self.mode == "auto":
                await self._auto_allocate_power(pv_excess)
            elif self.mode == "pv_priority":
                await self._pv_priority_allocate_power(pv_excess)
            elif self.mode == "battery_priority":
                await self._battery_priority_allocate_power(pv_excess)

        except Exception as e:
            _LOGGER.error("Error updating devices: %s", str(e))

    async def _update_device_state(self, device: EMSDevice) -> None:
        """Update a device's state."""
        try:
            # Update power consumption
            power_state = self.hass.states.get(device.power_sensor_entity)
            if power_state and power_state.state not in ["unknown", "unavailable"]:
                device.current_power = float(power_state.state)

            # Update auto-enabled status
            auto_state = self.hass.states.get(device.auto_switch_entity)
            if auto_state:
                device.is_auto_enabled = auto_state.state == "on"

            # Update active status
            device_state = self.hass.states.get(device.entity_id)
            if device_state:
                device.is_active = device_state.state == "on"

        except Exception as e:
            _LOGGER.error("Error updating device %s state: %s", device.name, str(e))

    async def _auto_allocate_power(self, pv_excess: float) -> None:
        """Auto-allocate power based on PV excess."""
        if pv_excess < 100:  # Minimum threshold
            return

        # Get power allocation
        allocation = self.priority_manager.allocate_power(pv_excess)

        # Apply allocation
        for device_id, allocated_power in allocation.items():
            device = next(
                (d for d in self.priority_manager.devices if d.device_id == device_id),
                None,
            )
            if device and device.is_auto_enabled:
                await self._turn_on_device(device, allocated_power)

    async def _pv_priority_allocate_power(self, pv_excess: float) -> None:
        """PV priority mode - use all available PV excess."""
        await self._auto_allocate_power(pv_excess)

    async def _battery_priority_allocate_power(self, pv_excess: float) -> None:
        """Battery priority mode - prioritize battery charging."""
        # Turn off all devices to maximize battery charging
        for device in self.priority_manager.devices:
            if device.is_active:
                await self._turn_off_device(device)

    async def _turn_on_device(
        self, device: EMSDevice, power_limit: Optional[float] = None
    ) -> None:
        """Turn on a device with optional power limit."""
        try:
            # Turn on the device
            await self.hass.services.async_call(
                "switch", "turn_on", {"entity_id": device.entity_id}
            )

            # Set power limit if specified
            if power_limit and power_limit < device.max_power:
                # This would require a power limiting service for the device
                pass

            device.is_active = True
            _LOGGER.debug("Turned on device %s", device.name)

        except Exception as e:
            _LOGGER.error("Error turning on device %s: %s", device.name, str(e))

    async def _turn_off_device(self, device: EMSDevice) -> None:
        """Turn off a device."""
        try:
            await self.hass.services.async_call(
                "switch", "turn_off", {"entity_id": device.entity_id}
            )
            device.is_active = False
            _LOGGER.debug("Turned off device %s", device.name)

        except Exception as e:
            _LOGGER.error("Error turning off device %s: %s", device.name, str(e))

    async def shutdown(self) -> None:
        """Shutdown the EMS system."""
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

        _LOGGER.info("EMS Manager shutdown complete")

    def get_entities(self) -> List[SensorEntity]:
        """Get all EMS entities."""
        return self.entities
