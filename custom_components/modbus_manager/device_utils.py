"""Device utilities for consistent device creation across all platforms."""

from typing import Any, Dict

from homeassistant.core import HomeAssistant

from .const import DOMAIN


def generate_unique_id(
    prefix: str, template_unique_id: str = None, name: str = None
) -> str:
    """Generate consistent unique_id across all platforms.

    Args:
        prefix: Device prefix (e.g., "SG", "SBR")
        template_unique_id: unique_id from template (optional)
        name: Fallback name if no template_unique_id (optional)

    Returns:
        Generated unique_id with prefix
    """
    if template_unique_id:
        # Check if template_unique_id already has prefix
        if template_unique_id.startswith(f"{prefix}_"):
            return template_unique_id
        else:
            return f"{prefix}_{template_unique_id}"
    else:
        # Fallback: Clean the name for unique_id
        if name:
            clean_name = (
                name.lower()
                .replace(" ", "_")
                .replace("-", "_")
                .replace("(", "")
                .replace(")", "")
            )
            return f"{prefix}_{clean_name}"
        else:
            return f"{prefix}_unknown"


def process_template_entities_with_prefix(
    entities: list, prefix: str, template_name: str = "unknown"
) -> list:
    """Process template entities and add prefix to unique_id and name.

    Args:
        entities: List of entity dictionaries from template
        prefix: Device prefix (e.g., "SG", "SBR")
        template_name: Template name for logging

    Returns:
        List of processed entities with prefix applied
    """
    processed_entities = []

    for entity in entities:
        processed_entity = entity.copy()

        # Process unique_id
        template_unique_id = entity.get("unique_id")
        if template_unique_id:
            if not template_unique_id.startswith(f"{prefix}_"):
                processed_entity["unique_id"] = f"{prefix}_{template_unique_id}"
        else:
            # Generate unique_id from name if not present
            name = entity.get("name", "unknown")
            clean_name = (
                name.lower()
                .replace(" ", "_")
                .replace("-", "_")
                .replace("(", "")
                .replace(")", "")
            )
            processed_entity["unique_id"] = f"{prefix}_{clean_name}"

        # Ensure default_entity_id is set (used to force entity_id)
        if "default_entity_id" not in processed_entity:
            default_entity_id = processed_entity.get("unique_id")
            processed_entity["default_entity_id"] = (
                default_entity_id.lower()
                if isinstance(default_entity_id, str)
                else default_entity_id
            )

        # Process name - avoid double prefixes
        template_name_value = entity.get("name")
        if template_name_value:
            # Check if name already starts with prefix to avoid double prefixes
            if not template_name_value.startswith(f"{prefix} "):
                processed_entity["name"] = f"{prefix} {template_name_value}"
            else:
                # Name already has prefix, keep it as is
                processed_entity["name"] = template_name_value

        processed_entities.append(processed_entity)

    return processed_entities


def replace_template_placeholders(
    template_string: str, prefix: str, slave_id: int = 1, battery_slave_id: int = 200
) -> str:
    """Replace template placeholders in strings with actual values.

    Args:
        template_string: String containing placeholders like {PREFIX}, {SLAVE_ID}
        prefix: Device prefix to replace {PREFIX}
        slave_id: Slave ID to replace {SLAVE_ID} (legacy, no longer used in register definitions)
        battery_slave_id: Battery slave ID to replace {BATTERY_SLAVE_ID} (legacy, no longer used)

    Returns:
        String with placeholders replaced

    Note:
        {SLAVE_ID} and {BATTERY_SLAVE_ID} are kept for backward compatibility but should
        not be used in new templates. slave_id is now always set from device config.
    """
    if not isinstance(template_string, str):
        return template_string

    # Replace common placeholders
    # Note: {PREFIX} is still actively used, {SLAVE_ID} and {BATTERY_SLAVE_ID} are legacy
    replacements = {
        "{PREFIX}": prefix,
        "{SLAVE_ID}": str(slave_id),  # Legacy - no longer used in templates
        "{BATTERY_SLAVE_ID}": str(battery_slave_id),  # Legacy - no longer used
    }

    result = template_string
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)

    return result


def generate_entity_name(prefix: str, name: str) -> str:
    """Generate consistent entity name across all platforms.

    Args:
        prefix: Device prefix (e.g., "SG", "SBR")
        name: Base name from template

    Returns:
        Generated entity name with prefix
    """
    return f"{prefix} {name}"


def generate_entity_id(platform: str, unique_id: str) -> str:
    """Generate consistent entity_id across all platforms.

    Args:
        platform: Platform name (e.g., "sensor", "switch", "select")
        unique_id: Generated unique_id

    Returns:
        Generated entity_id
    """
    return f"{platform}.{unique_id}"


def create_device_info_dict(
    hass: HomeAssistant,
    host: str,
    port: int,
    slave_id: int,
    prefix: str,
    template_name: str,
    firmware_version: str = None,
    config_entry_id: str = None,
) -> Dict[str, Any]:
    """Create device info dict using the device factory.

    This is a convenience function that creates device info using the
    centralized device factory and converts it to a dict format that
    can be used by all platforms.

    Args:
        firmware_version: Firmware version from config entry or register.
                         If None, defaults to "1.0.0".
    """
    # Create device identifier
    device_identifier = f"modbus_manager_{host}_{port}_slave_{slave_id}"

    # Don't create a separate hub device - just use the hub identifier for linking
    # The hub is managed by the Modbus connection in __init__.py

    # Use firmware version from config or default
    if firmware_version is None:
        firmware_version = "1.0.0"

    # Return device info as dict - no separate hub device needed
    # Device name is set to prefix only, so with has_entity_name=True,
    # friendly_name will be "{prefix} {entity.name}" instead of "{prefix} ({template_name}) {entity.name}"
    return {
        "identifiers": {(DOMAIN, device_identifier)},
        "name": prefix,  # Use prefix only to keep friendly_name short: "Prefix Entityname"
        "manufacturer": "Modbus Manager",
        "model": f"{template_name} (Slave {slave_id})",
        "sw_version": f"Firmware: {firmware_version}",
    }


def create_base_extra_state_attributes(
    unique_id: str,
    register_config: Dict[str, Any],
    scan_interval: Any = None,
    additional_attributes: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Create base extra_state_attributes dict with common attributes for all entities.

    This centralizes the common attributes to avoid duplication across entity classes.
    Entity-specific attributes can be added via additional_attributes parameter.

    Args:
        unique_id: The entity's unique_id
        register_config: Register configuration dict containing address, data_type, etc.
        scan_interval: Scan interval value (optional, can be in register_config)
        additional_attributes: Optional dict of entity-specific attributes to merge

    Returns:
        Dict with common extra_state_attributes that can be used by all entity types
    """
    # Ensure unique_id is lowercase in attributes
    unique_id_lower = unique_id.lower() if isinstance(unique_id, str) else unique_id

    base_attributes = {
        "unique_id": unique_id_lower,
    }

    # Only add fields if they have values (not None)
    if register_config.get("address") is not None:
        base_attributes["register_address"] = register_config.get("address")
    if register_config.get("data_type") is not None:
        base_attributes["data_type"] = register_config.get("data_type")
    if register_config.get("slave_id") is not None:
        base_attributes["slave_id"] = register_config.get("slave_id")
    if register_config.get("input_type") is not None:
        base_attributes["input_type"] = register_config.get("input_type")
    # Static configuration values
    if register_config.get("scale") is not None:
        base_attributes["scale"] = register_config.get("scale")
    if register_config.get("offset") is not None:
        base_attributes["offset"] = register_config.get("offset")
    if register_config.get("precision") is not None:
        base_attributes["precision"] = register_config.get("precision")
    if register_config.get("group") is not None:
        base_attributes["group"] = register_config.get("group")
    scan_interval_value = scan_interval or register_config.get("scan_interval")
    if scan_interval_value is not None:
        base_attributes["scan_interval"] = scan_interval_value
    if register_config.get("swap") is not None:
        base_attributes["swap"] = register_config.get("swap")

    # Merge additional entity-specific attributes if provided
    if additional_attributes:
        base_attributes.update(additional_attributes)

    return base_attributes
