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
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TIMEOUT = "timeout"
CONF_RETRIES = "retries"
CONF_RETRY_DELAY = "retry_delay"

# Defaults
DEFAULT_NAME = "Modbus Device"
DEFAULT_PORT = 502
DEFAULT_SLAVE_ID = 1
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
DEFAULT_TIMEOUT = 3
DEFAULT_RETRIES = 3
DEFAULT_RETRY_DELAY = 0.1

# Limits
MIN_SLAVE_ID = 1
MAX_SLAVE_ID = 247

# Error Messages
ERROR_INVALID_HOST = "invalid_host"
ERROR_INVALID_PORT = "invalid_port"
ERROR_INVALID_SLAVE_ID = "invalid_slave_id"
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_UNKNOWN = "unknown"
ERROR_ALREADY_CONFIGURED = "already_configured"

# Timeouts
REGISTER_CACHE_TIMEOUT = timedelta(seconds=5)
OPERATION_TIMEOUT = timedelta(seconds=30)
RECONNECT_DELAY = timedelta(seconds=60)
METRICS_RESPONSE_TIME = timedelta(seconds=60)
LOGGER_COMMUNICATION = timedelta(seconds=60)

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

# Modbus specific
MAX_REGISTERS_PER_READ = 60  # Modbus Spezifikation: Max. 125 Register pro Lesevorgang

# Register Types
REGISTER_TYPE_HOLDING = "holding"
REGISTER_TYPE_INPUT = "input"
REGISTER_TYPE_COIL = "coil"
REGISTER_TYPE_DISCRETE = "discrete"

# Data Types
DATA_TYPE_INT16 = "int16"
DATA_TYPE_UINT16 = "uint16"
DATA_TYPE_INT32 = "int32"
DATA_TYPE_UINT32 = "uint32"
DATA_TYPE_INT64 = "int64"
DATA_TYPE_UINT64 = "uint64"
DATA_TYPE_FLOAT32 = "float32"
DATA_TYPE_FLOAT64 = "float64"
DATA_TYPE_STRING = "string"

# Event Types
EVENT_DEVICE_STATUS_CHANGED = f"{DOMAIN}_device_status_changed"
EVENT_REGISTER_UPDATED = f"{DOMAIN}_register_updated"
EVENT_ERROR_OCCURRED = f"{DOMAIN}_error_occurred"

# Service Names
SERVICE_RELOAD = "reload"
SERVICE_SYNC_TIME = "sync_device_time"
SERVICE_BATCH_READ = "batch_read"
SERVICE_TEST_DEVICE_TYPE = "test_device_type"

# Polling Groups
POLLING_GROUP_FAST = "fast"
POLLING_GROUP_NORMAL = "normal"
POLLING_GROUP_SLOW = "slow" 