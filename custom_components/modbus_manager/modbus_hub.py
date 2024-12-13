"""Modbus Manager Hub for managing Modbus connections."""
import logging
from pymodbus.client.tcp import AsyncModbusTcpClient
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from datetime import timedelta
import yaml
from pathlib import Path
import asyncio

_LOGGER = logging.getLogger(__name__)

class ModbusManagerHub:
    """Class for managing Modbus connection for devices."""

    def __init__(self, name, host, port, slave, device_type, hass):
        """Initialize the hub."""
        self.name = name
        self.host = host
        self.port = port
        self.slave = slave
        self.device_type = device_type
        self.hass = hass
        self.client = None
        self.coordinators = {}
        self._device_definition_cache = {}  # Cache for device definitions 