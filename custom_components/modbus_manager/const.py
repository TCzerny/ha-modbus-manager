"""Constants for the Modbus Manager integration."""
from typing import Final
from enum import Enum
from homeassistant.const import Platform

DOMAIN: Final = "modbus_manager"
CONF_DEVICE_TYPE: Final = "device_type"

# Configuration keys
CONF_SERVICES: Final = "services"
CONF_REGISTER: Final = "register"
CONF_MIN: Final = "min"
CONF_MAX: Final = "max"
CONF_STEP: Final = "step"
CONF_OPTIONS: Final = "options"
CONF_HUB: Final = "hub"
CONF_SLAVE_ID: Final = "slave_id"
CONF_ADDRESS: Final = "address"
CONF_DATA_TYPE: Final = "data_type"
CONF_SCALE: Final = "scale"
CONF_PRECISION: Final = "precision"
CONF_MIN_VALUE: Final = "min_value"
CONF_MAX_VALUE: Final = "max_value"
CONF_GROUP: Final = "group"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_INPUT_TYPE: Final = "input_type"
CONF_UNIT_OF_MEASUREMENT: Final = "unit_of_measurement"
CONF_DEVICE_CLASS: Final = "device_class"
CONF_STATE_CLASS: Final = "state_class"

# Service types
SERVICE_TYPE_NUMBER: Final = "number"
SERVICE_TYPE_SELECT: Final = "select"
SERVICE_TYPE_BUTTON: Final = "button"

# Default values
DEFAULT_TIMEOUT: Final = 3  # Sekunden
MIN_TIMEOUT: Final = 1  # Minimum timeout in seconds
MAX_TIMEOUT: Final = 30  # Maximum timeout in seconds
DEFAULT_DELAY: Final = 0  # Default delay in seconds
MIN_DELAY: Final = 0  # Minimum delay in seconds
DEFAULT_MESSAGE_WAIT_MS: Final = 100  # Default message wait in milliseconds
MIN_MESSAGE_WAIT_MS: Final = 10  # Minimum message wait in milliseconds
MAX_MESSAGE_WAIT_MS: Final = 1000  # Maximum message wait in milliseconds
DEFAULT_RETRY_ON_EMPTY: Final = True
DEFAULT_RETRIES: Final = 3
DEFAULT_RETRY_DELAY: Final = 0.1

# Standard-Werte
DEFAULT_SLAVE = 1
DEFAULT_PORT = 502

# Service Namen
SERVICE_SET_BATTERY_MODE = "set_battery_mode"
SERVICE_SET_INVERTER_MODE = "set_inverter_mode"
SERVICE_SET_EXPORT_POWER_LIMIT = "set_export_power_limit"

# Event Namen
EVENT_MODBUS_MANAGER_REGISTER_UPDATED = "modbus_manager_register_updated"
EVENT_MODBUS_MANAGER_DEVICE_UPDATED = "modbus_manager_device_updated"
EVENT_MODBUS_MANAGER_ERROR = "modbus_manager_error"

# Platforms used by this integration
PLATFORMS = [
    Platform.SENSOR, 
    Platform.NUMBER, 
    Platform.SWITCH, 
    Platform.SELECT,
    Platform.BINARY_SENSOR,
    Platform.BUTTON
]

# Neue Entity-Typen basierend auf modbus_connect
class EntityType(Enum):
    """Definiert die verschiedenen Entity-Typen."""
    SENSOR = "sensor"
    NUMBER = "number"
    SWITCH = "switch"
    SELECT = "select"
    BINARY_SENSOR = "binary_sensor"
    BUTTON = "button"

# Erweiterte Datenverarbeitungsoptionen
class DataProcessingType(Enum):
    """Definiert die verschiedenen Datenverarbeitungsoptionen."""
    SCALE = "scale"
    OFFSET = "offset"
    SUM_SCALE = "sum_scale"
    SHIFT_BITS = "shift_bits"
    BITS = "bits"
    MULTIPLIER = "multiplier"
    PRECISION = "precision"
    SWAP = "swap"
    BIT_MASK = "bitmask"
    BIT_POSITION = "bit_position"
    BIT_SHIFT = "bit_shift"
    BIT_ROTATE = "bit_rotate"
    BIT_RANGE = "bit_range"

# Byte-Reihenfolge für Float-Werte
class ByteOrder(Enum):
    """Definiert die verschiedenen Byte-Reihenfolgen."""
    BIG_ENDIAN = "big"           # ABCD - Standard
    LITTLE_ENDIAN = "little"     # DCBA - Umgekehrte Reihenfolge
    BIG_ENDIAN_SWAP = "big_swap" # BADC - Big Endian mit Wortvertauschung
    LITTLE_ENDIAN_SWAP = "little_swap" # CDAB - Little Endian mit Wortvertauschung

# Control-Typen für read/write Register
class ControlType(Enum):
    """Definiert die verschiedenen Control-Typen."""
    NONE = "none"
    NUMBER = "number"
    SELECT = "select"
    SWITCH = "switch"
    TEXT = "text"

# Daten-Typen
class DataType(Enum):
    """Definiert die verschiedenen Daten-Typen."""
    UINT16 = "uint16"
    INT16 = "int16"
    UINT32 = "uint32"
    INT32 = "int32"
    FLOAT = "float"        # IEEE 754 32-bit float
    FLOAT64 = "float64"    # IEEE 754 64-bit float
    STRING = "string"
    BOOLEAN = "boolean"

# Register-Typen
class RegisterType(Enum):
    """Definiert die verschiedenen Register-Typen."""
    INPUT = "input"
    HOLDING = "holding"
    COIL = "coil"
    DISCRETE = "discrete"

class NameType(Enum):
    """Definiert die verschiedenen Typen von Namen/IDs."""
    ENTITY_ID = "entity_id"          # Für Entity IDs (z.B. sensor.sungrow_inverter_battery_level)
    UNIQUE_ID = "unique_id"          # Für eindeutige IDs (z.B. sungrow_inverter_battery_level)
    DISPLAY_NAME = "display_name"    # Für UI-Anzeigenamen (z.B. Sungrow Battery Level)
    BASE_NAME = "base_name"          # Für interne Referenzen (z.B. sungrow_battery_level)
    REGISTER = "register"            # Für Register-Namen (z.B. battery_level)
    SERVICE_NAME = "service_name"    # Für Service-Namen (z.B. set_battery_level)

# Standard-Werte für neue Features
DEFAULT_UPDATE_INTERVAL = 10  # Sekunden - Reduced for better control responsiveness
DEFAULT_MAX_REGISTER_READ = 8  # Maximale Register pro Read
DEFAULT_PRECISION = 2  # Standard-Präzision
DEFAULT_MIN_VALUE = 0.0  # Standard-Minimum
DEFAULT_MAX_VALUE = 100.0  # Standard-Maximum
