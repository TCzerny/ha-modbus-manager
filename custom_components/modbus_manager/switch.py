"""Modbus Manager Coordinator Switch Platform."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ModbusCoordinator
from .device_utils import create_base_extra_state_attributes, is_coordinator_connected
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up Modbus Manager coordinator switches from a config entry."""
    coordinator: ModbusCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Get all entities from coordinator (structured dict)
    entities_dict = await coordinator._collect_all_registers()

    # Get controls and filter for switch type
    controls = entities_dict.get("controls", [])
    switch_controls = [c for c in controls if c.get("type") == "switch"]

    entities_by_subentry: dict[str | None, list] = {}

    for register_config in switch_controls:
        try:
            entity = ModbusCoordinatorSwitch(coordinator, register_config)
            subentry_id = register_config.get("config_subentry_id")
            entities_by_subentry.setdefault(subentry_id, []).append(entity)
            _LOGGER.debug(
                "ModbusCoordinatorSwitch created: %s (key: %s)",
                entity.name,
                entity._register_key,
            )
        except Exception as e:
            _LOGGER.error(
                "Error creating switch %s: %s",
                register_config.get("name", "unknown"),
                str(e),
            )

    entities_count = 0
    for subentry_id, entities in entities_by_subentry.items():
        if not entities:
            continue
        entities_count += len(entities)
        if subentry_id:
            async_add_entities(entities, config_subentry_id=subentry_id)
        else:
            async_add_entities(entities)
    if entities_count:
        _LOGGER.debug("Created %d coordinator switches", entities_count)
    else:
        _LOGGER.debug("No coordinator switches created")


class ModbusCoordinatorSwitch(SwitchEntity):
    """Representation of a Modbus Coordinator Switch."""

    def __init__(self, coordinator: ModbusCoordinator, register_config: dict[str, Any]):
        """Initialize the coordinator switch."""
        self._coordinator = coordinator
        self._register_config = register_config

        # Extract basic properties
        # unique_id is already processed by coordinator with prefix via _process_entities_with_prefix
        self._name = register_config.get("name", "Unknown Switch")
        self._unique_id = register_config.get("unique_id", "unknown")
        self._address = register_config.get("address", 0)
        self._input_type = register_config.get("input_type", "holding")
        self._data_type = register_config.get("data_type", "uint16")
        self._scan_interval = register_config.get("scan_interval", 30)

        # Get write values
        self._write_value = register_config.get("write_value", 1)
        self._write_value_off = register_config.get("write_value_off", 0)

        # Get on_value and off_value for state interpretation
        # If not specified, use write_value/write_value_off as fallback
        self._on_value = register_config.get("on_value", self._write_value)
        self._off_value = register_config.get("off_value", self._write_value_off)

        # Create register key for coordinator lookup
        self._register_key = f"{self._unique_id}_{self._address}"

        # Set entity properties
        self._attr_has_entity_name = True
        self._attr_name = self._name
        self._attr_unique_id = self._unique_id
        default_entity_id = register_config.get("default_entity_id")
        if default_entity_id:
            if isinstance(default_entity_id, str):
                default_entity_id = default_entity_id.lower()
            if "." in default_entity_id:
                self.entity_id = default_entity_id
            else:
                self.entity_id = f"switch.{default_entity_id}"

        # Write each update to the state machine, even if the data is the same.
        self._attr_force_update = register_config.get("force_update", False)

        # Set entity category:
        # - None (default): Primary sensors that represent main data points.
        # - diagnostic: Used for read-only information about the device’s health or status.
        # - config: Used for entities that change how a device behaves.
        # An entity with a category will:
        # - Not be exposed to cloud, Alexa, or Google Assistant components.
        # - Not be included in indirect service calls to devices or areas.
        entity_category_str = register_config.get("entity_category")
        if entity_category_str == "diagnostic":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif entity_category_str == "config":
            self._attr_entity_category = EntityCategory.CONFIG
        else:
            self._attr_entity_category = None

        # Get device info from register_config (provided by coordinator)
        device_info = register_config.get("device_info")
        if not device_info:
            _LOGGER.error(
                "Switch %s missing device_info. Coordinator should provide this.",
                self._name,
            )
            raise ValueError("device_info missing from coordinator")
        self._attr_device_info = DeviceInfo(**device_info)

        # Minimize extra_state_attributes - only include static/essential attributes
        # Ensure slave_id is in register_config for base attributes
        register_config_with_slave = register_config.copy()
        if "slave_id" not in register_config_with_slave:
            register_config_with_slave["slave_id"] = coordinator.entry.data.get(
                "slave_id", 1
            )

        self._attr_extra_state_attributes = create_base_extra_state_attributes(
            unique_id=self._attr_unique_id,
            register_config=register_config_with_slave,
            scan_interval=self._scan_interval,
            additional_attributes={
                # Switch-specific static values
                "on_value": self._on_value,
                "off_value": self._off_value,
                "write_value": self._write_value,
                "write_value_off": self._write_value_off,
            },
        )

        # Add optional attributes if present
        if register_config.get("map"):
            self._attr_extra_state_attributes["map"] = register_config["map"]
        if register_config.get("flags"):
            self._attr_extra_state_attributes["flags"] = register_config["flags"]
        if register_config.get("options"):
            self._attr_extra_state_attributes["options"] = register_config["options"]

    @property
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        if not self._coordinator.data:
            return None

        register_data = self._coordinator.data.get(self._register_key)
        if register_data is None:
            return None

        # Extract the processed value
        processed_value = register_data.get("processed_value")
        if processed_value is None:
            return None

        # Use on_value and off_value for state interpretation
        # These are automatically set from write_value/write_value_off if not specified
        if self._on_value is not None and self._off_value is not None:
            if isinstance(processed_value, (int, float)):
                # Compare numeric values directly
                if processed_value == self._on_value:
                    return True
                elif processed_value == self._off_value:
                    return False
                else:
                    # Value doesn't match expected on/off values
                    # Return None to indicate unknown state (HA-compliant)
                    _LOGGER.debug(
                        "Switch %s has unexpected value %s (expected %s or %s) - state unknown",
                        self._name,
                        processed_value,
                        self._on_value,
                        self._off_value,
                    )
                    return None
            elif isinstance(processed_value, str):
                # Try to convert string to int for comparison
                try:
                    int_value = int(processed_value)
                    if int_value == self._on_value:
                        return True
                    elif int_value == self._off_value:
                        return False
                    else:
                        return None
                except (ValueError, TypeError):
                    return None
            else:
                return None

        # Default behavior: Convert to boolean based on data type and value
        if isinstance(processed_value, bool):
            return processed_value
        elif isinstance(processed_value, (int, float)):
            # For numeric values, consider 0 as False, anything else as True
            return bool(processed_value)
        elif isinstance(processed_value, str):
            # For string values, consider empty string as False, anything else as True
            return bool(processed_value.strip())
        else:
            return None

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return (
            is_coordinator_connected(self._coordinator)
            and self._coordinator.last_update_success
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            # Write to Modbus register using write_value
            await self._write_register(self._write_value)

        except Exception as e:
            _LOGGER.error("Error turning on switch %s: %s", self._name, str(e))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            # Write to Modbus register using write_value_off
            await self._write_register(self._write_value_off)

        except Exception as e:
            _LOGGER.error("Error turning off switch %s: %s", self._name, str(e))

    async def _write_register(self, value: int) -> None:
        """Write value to Modbus register."""
        try:
            from .modbus_utils import encode_register_write_value, get_write_call_type

            # Check for custom write function code
            write_function_code = self._register_config.get("write_function_code")
            write_value, count = encode_register_write_value(
                value, self._register_config
            )

            call_type = get_write_call_type(count, write_function_code)

            if write_function_code:
                _LOGGER.debug(
                    "Using custom write function code %d for register %d",
                    write_function_code,
                    self._address,
                )

            # Get slave ID
            slave_id = self._register_config.get("slave_id", 1)

            # Write to register
            await self._coordinator.hub.async_pb_call(
                slave_id,
                self._address,
                write_value,
                call_type,
            )

            _LOGGER.debug(
                "Wrote value %d to register %d (slave_id: %d)",
                value,
                self._address,
                slave_id,
            )

        except Exception as e:
            _LOGGER.error(
                "Error writing to register %d: %s",
                self._address,
                str(e),
            )
            raise

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            # Update raw/processed/numeric values in attributes if available
            if self._coordinator.data:
                register_data = self._coordinator.data.get(self._register_key)
                if register_data:
                    raw_value = register_data.get("raw_value")
                    processed_value = register_data.get("processed_value")
                    numeric_value = register_data.get("numeric_value")

                    # Update extra_state_attributes with raw/processed/numeric values
                    self._attr_extra_state_attributes = {
                        **self._attr_extra_state_attributes,
                        "raw_value": raw_value if raw_value is not None else "N/A",
                        "processed_value": processed_value
                        if processed_value is not None
                        else "N/A",
                    }
                    if numeric_value is not None:
                        self._attr_extra_state_attributes[
                            "numeric_value"
                        ] = numeric_value
        except Exception as e:
            _LOGGER.debug("Error updating switch attributes: %s", str(e))

        self.async_write_ha_state()
