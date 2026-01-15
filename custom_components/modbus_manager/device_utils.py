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
        Generated unique_id with prefix (all lowercase for consistency)
    """
    # Convert prefix to lowercase for consistent unique_id format
    prefix_lower = prefix.lower()

    if template_unique_id:
        # Check if template_unique_id already has prefix (case-insensitive)
        if template_unique_id.lower().startswith(f"{prefix_lower}_"):
            # unique_id already has prefix, but ensure it's lowercase
            return template_unique_id.lower()
        else:
            return f"{prefix_lower}_{template_unique_id}"
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
            return f"{prefix_lower}_{clean_name}"
        else:
            return f"{prefix_lower}_unknown"


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
        # Convert prefix to lowercase for consistent unique_id format
        prefix_lower = prefix.lower()
        template_unique_id = entity.get("unique_id")
        if template_unique_id:
            # Check if unique_id already has prefix (case-insensitive check)
            if not template_unique_id.lower().startswith(f"{prefix_lower}_"):
                processed_entity["unique_id"] = f"{prefix_lower}_{template_unique_id}"
            else:
                # unique_id already has prefix, but ensure it's lowercase
                processed_entity["unique_id"] = template_unique_id.lower()
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
            processed_entity["unique_id"] = f"{prefix_lower}_{clean_name}"

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
    # Device name includes full template name for better UI display
    # Eindeutigkeit wird durch unique_id sichergestellt (enthält bereits prefix)
    # Device identifiers (host, port, slave_id) stellen auch Eindeutigkeit sicher
    return {
        "identifiers": {(DOMAIN, device_identifier)},
        "name": f"{prefix} ({template_name})",  # Full name for better UI display
        "manufacturer": "Modbus Manager",
        "model": f"{template_name} (Slave {slave_id})",
        "sw_version": f"Firmware: {firmware_version}",
    }
