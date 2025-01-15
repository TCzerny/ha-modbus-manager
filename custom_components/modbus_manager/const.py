"""Constants for the Modbus Manager integration."""
from typing import Final

DOMAIN: Final = "modbus_manager"
CONF_DEVICE_TYPE: Final = "device_type"

# Default values
DEFAULT_TIMEOUT: Final = 3  # Sekunden
DEFAULT_RETRY_ON_EMPTY: Final = True
DEFAULT_RETRIES: Final = 3
DEFAULT_RETRY_DELAY: Final = 0.1
