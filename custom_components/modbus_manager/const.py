"""Constants for the Modbus Manager integration."""
from datetime import timedelta

DOMAIN = "modbus_manager"
VERSION = "1.0.0"

# Configuration
CONF_NAME = "name"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_SLAVE = "slave"
CONF_DEVICE_TYPE = "device_type"

# Defaults
DEFAULT_NAME = "Modbus Device"
DEFAULT_PORT = 502
DEFAULT_SLAVE_ID = 1
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_TIMEOUT = 3
DEFAULT_RETRIES = 3

# Limits
MIN_SLAVE_ID = 1
MAX_SLAVE_ID = 247

# Error Messages
ERROR_INVALID_HOST = "invalid_host"
ERROR_INVALID_PORT = "invalid_port"
ERROR_INVALID_SLAVE_ID = "invalid_slave_id"
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_UNKNOWN = "unknown"

# Timeouts
REGISTER_CACHE_TIMEOUT = timedelta(seconds=300)
OPERATION_TIMEOUT = timedelta(seconds=30)
RECONNECT_DELAY = timedelta(seconds=60)

# Statistics
STAT_DAILY = "daily"
STAT_WEEKLY = "weekly"
STAT_MONTHLY = "monthly"
STAT_YEARLY = "yearly"
STAT_TYPES = [STAT_DAILY, STAT_WEEKLY, STAT_MONTHLY, STAT_YEARLY]

# Device Types
DEVICE_TYPES = {
    "sungrow_shrt": "Sungrow SH-RT Hybrid Inverter",
    "sungrow_battery": "Sungrow Battery System",
    "compleo_ebox": "Compleo eBox",
}

# Template Types
TEMPLATE_ENERGY = "energy"
TEMPLATE_POWER = "power"
TEMPLATE_STATUS = "status" 