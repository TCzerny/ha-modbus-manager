"""Constants for the Modbus Manager integration."""
from typing import Final
from datetime import timedelta

DOMAIN: Final = "modbus_manager"
VERSION: Final = "1.0.0"

# Configuration
CONF_DEVICE_TYPE: Final = "device_type"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_TCP_TIMEOUT: Final = "tcp_timeout"
CONF_RETRIES: Final = "retries"
CONF_RETRY_DELAY: Final = "retry_delay"
CONF_USE_LOCAL_TIME: Final = "use_local_time"

# Defaults
DEFAULT_SCAN_INTERVAL: Final = 30
DEFAULT_TCP_TIMEOUT: Final = 3
DEFAULT_RETRIES: Final = 3
DEFAULT_RETRY_DELAY: Final = 0.1
DEFAULT_PORT: Final = 502
DEFAULT_SLAVE_ID: Final = 1
DEFAULT_NAME: Final = "Modbus Device"

# Modbus Limits
MAX_REGISTERS_PER_READ: Final = 125
MIN_REGISTER_ADDRESS: Final = 0
MAX_REGISTER_ADDRESS: Final = 65535
MIN_SLAVE_ID: Final = 1
MAX_SLAVE_ID: Final = 247

# Update Intervals
FAST_UPDATE_INTERVAL: Final = timedelta(seconds=10)
NORMAL_UPDATE_INTERVAL: Final = timedelta(seconds=30)
SLOW_UPDATE_INTERVAL: Final = timedelta(seconds=300)

# Device Types
DEVICE_TYPES: Final = {
    "generic": "Generic Modbus Device",
    "sungrow_shrt": "Sungrow SH-RT Hybrid Inverter",
    "sungrow_battery": "Sungrow Battery System"
}

# Register Types
REGISTER_TYPE_HOLDING: Final = "holding"
REGISTER_TYPE_INPUT: Final = "input"
REGISTER_TYPE_COIL: Final = "coil"
REGISTER_TYPE_DISCRETE: Final = "discrete"

# Data Types
DATA_TYPE_UINT16: Final = "uint16"
DATA_TYPE_INT16: Final = "int16"
DATA_TYPE_UINT32: Final = "uint32"
DATA_TYPE_INT32: Final = "int32"
DATA_TYPE_FLOAT: Final = "float"
DATA_TYPE_STRING: Final = "string"
DATA_TYPE_BOOL: Final = "bool"

# Error Messages
ERROR_INVALID_HOST: Final = "invalid_host"
ERROR_INVALID_PORT: Final = "invalid_port"
ERROR_INVALID_SLAVE_ID: Final = "invalid_slave_id"
ERROR_CANNOT_CONNECT: Final = "cannot_connect"
ERROR_UNKNOWN: Final = "unknown"
ERROR_ALREADY_CONFIGURED: Final = "already_configured"

# Event Types
EVENT_DEVICE_ERROR: Final = "modbus_manager_device_error"
EVENT_COMMUNICATION_ERROR: Final = "modbus_manager_communication_error"
EVENT_VALUE_UPDATED: Final = "modbus_manager_value_updated"

# Service Names
SERVICE_RELOAD: Final = "reload"
SERVICE_SYNC_TIME: Final = "sync_device_time"
SERVICE_BATCH_READ: Final = "batch_read"

# Cache Settings
DEVICE_DEFINITION_CACHE_TIMEOUT: Final = timedelta(minutes=5)
REGISTER_CACHE_TIMEOUT: Final = timedelta(seconds=5)

# Performance Metrics
METRICS_RESPONSE_TIME: Final = "response_time"
METRICS_ERROR_RATE: Final = "error_rate"
METRICS_SUCCESS_RATE: Final = "success_rate"
METRICS_TOTAL_READS: Final = "total_reads"
METRICS_FAILED_READS: Final = "failed_reads"

# Logger Names
LOGGER_OPERATIONS: Final = "operations"
LOGGER_COMMUNICATION: Final = "communication"
LOGGER_DEVICE: Final = "device" 