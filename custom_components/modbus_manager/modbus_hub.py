"""Modbus Manager Hub for managing Modbus connections."""
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path

import yaml
import asyncio
from pymodbus.client.tcp import AsyncModbusTcpClient
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .errors import ModbusDeviceError, handle_modbus_error
from .logger import ModbusManagerLogger
from .optimization import ModbusManagerOptimizer
from .proxy import ModbusManagerProxy
from .device import ModbusManagerDevice

_LOGGER = logging.getLogger(__name__)

class ModbusManagerHub:
    """Class for managing Modbus connection for devices."""

    def __init__(self, name: str, host: str, port: int, slave: int, device_type: str, hass: HomeAssistant):
        """Initialize the hub.
        
        Args:
            name: Name of the device
            host: Hostname or IP address
            port: TCP port number
            slave: Modbus slave ID
            device_type: Type of device from device definitions
            hass: HomeAssistant instance
        """
        self.name = name
        self.host = host
        self.port = port
        self.slave = slave
        self.device_type = device_type
        self.hass = hass
        self.client: Optional[AsyncModbusTcpClient] = None
        self.coordinators: Dict[str, DataUpdateCoordinator] = {}
        self._device_definition_cache: Dict[str, Any] = {}
        self.logger = ModbusManagerLogger(f"hub_{name}")
        self.logger.debug(
            "Initializing hub", 
            name=name, 
            host=host, 
            port=port, 
            slave=slave,
            device_type=device_type
        )
        self.optimizer = ModbusManagerOptimizer()
        self.is_connected = False
        self.last_connect_attempt: Optional[datetime] = None
        self.reconnect_count = 0
        self.config: Dict[str, Any] = {}
        self.device_info: Dict[str, Any] = {}
        self._shutdown = False
        self.proxy: Optional[ModbusManagerProxy] = None
        self.device: Optional[ModbusManagerDevice] = None

    async def async_setup(self) -> bool:
        """Set up the Modbus connection with retry logic."""
        try:
            _LOGGER.debug("Setting up hub connection")
            # Load device configuration
            device_def = self.get_device_definition(self.device_type)
            if not device_def:
                raise UpdateFailed(f"No device definition found for {self.device_type}")
            
            self.device_info = device_def.get("device_info", {})
            self.config = device_def.get("config", {})

            # Initialize connection
            retry_count = 0
            max_retries = self.config.get("retries", 3)
            retry_delay = self.config.get("retry_delay", 0.1)

            while retry_count <= max_retries:
                try:
                    self.client = AsyncModbusTcpClient(
                        self.host,
                        self.port,
                        timeout=self.config.get("tcp_timeout", 3),
                        retries=0,
                        retry_on_empty=True,
                        close_comm_on_error=True
                    )
                    self.last_connect_attempt = datetime.now()
                    connected = await self.client.connect()
                    
                    if connected:
                        self.is_connected = True
                        _LOGGER.info("Connected to Modbus device at %s:%s", self.host, self.port)
                        self.proxy = ModbusManagerProxy(
                            self.client,
                            self.slave,
                            cache_timeout=self.config.get("cache_timeout", 60)
                        )
                        self.device = ModbusManagerDevice(self.hass, self.config)
                        _LOGGER.info("Hub setup complete")
                        return True
                        
                except Exception as e:
                    _LOGGER.warning("Connection attempt failed: %s", str(e))
                    
                retry_count += 1
                self.reconnect_count += 1
                
                if retry_count <= max_retries:
                    await asyncio.sleep(retry_delay * retry_count)
                    
            raise ConnectionError("Maximum number of connection attempts reached")
            
        except Exception as e:
            error = handle_modbus_error(e)
            _LOGGER.error("Hub setup failed: %s", str(error))
            raise error

    async def async_teardown(self) -> None:
        """Close the Modbus connection."""
        self._shutdown = True
        if self.client:
            self.is_connected = False
            try:
                await self.client.close()
                _LOGGER.info("Modbus connection closed for %s", self.name)
            except Exception as e:
                _LOGGER.warning("Error closing Modbus connection for %s: %s", self.name, e)

    def get_device_definition(self, device_definition_name: str) -> Optional[Dict[str, Any]]:
        """Get device configuration with caching."""
        if device_definition_name in self._device_definition_cache:
            return self._device_definition_cache[device_definition_name]

        definition_path = Path(__file__).parent / "device_definitions" / f"{device_definition_name}.yaml"
        if not definition_path.exists():
            _LOGGER.error("Device configuration file %s does not exist", definition_path)
            return None

        try:
            with open(definition_path, "r") as f:
                definition = yaml.safe_load(f)
                
            # Add prefix to all template names
            if 'helpers' in definition and 'templates' in definition['helpers']:
                for template in definition['helpers']['templates']:
                    template['name'] = f"{self.name}_{template['name']}"
                    template['unique_id'] = f"{self.name}_{template['unique_id']}"
                    
            # Add prefix to all automation names
            if 'automations' in definition:
                for automation in definition['automations']:
                    automation['name'] = f"{self.name}_{automation['name']}"
                    automation['unique_id'] = f"{self.name}_{automation['unique_id']}"
                    
                    # Update entity_ids in triggers and conditions
                    self._update_entity_references(automation)
                    
            self._device_definition_cache[device_definition_name] = definition
            return definition
            
        except Exception as e:
            _LOGGER.error("Error loading device definition: %s", e)
            return None

    def _update_entity_references(self, config: Dict[str, Any]) -> None:
        """Update entity references in automations and scripts."""
        if isinstance(config, dict):
            for key, value in config.items():
                if key == "entity_id" and isinstance(value, str):
                    if "." in value:
                        domain, entity = value.split(".", 1)
                        config[key] = f"{domain}.{self.name}_{entity}"
                elif isinstance(value, (dict, list)):
                    self._update_entity_references(value)
        elif isinstance(config, list):
            for item in config:
                if isinstance(item, (dict, list)):
                    self._update_entity_references(item)

    async def read_registers(self, device_definition_name: str) -> DataUpdateCoordinator:
        """Set up register reading with coordinator."""
        try:
            _LOGGER.debug("Creating coordinator for %s", self.name)
            
            coordinator = DataUpdateCoordinator(
                self.hass,
                _LOGGER,
                name=f"{self.name} Data",
                update_method=lambda: self._async_update_data(device_definition_name),
                update_interval=timedelta(seconds=self.config.get("scan_interval", 30)),
            )
            
            await coordinator.async_refresh()
            self.coordinators[self.name] = coordinator
            
            return coordinator
            
        except Exception as e:
            error = handle_modbus_error(e)
            
            raise error

    async def _async_update_data(self, device_definition_name: str) -> Dict[str, Any]:
        """Update data from Modbus device."""
        start_time = time.time()
        
        try:
            device_def = self.get_device_definition(device_definition_name)
            if not device_def:
                raise UpdateFailed("No device configuration found")

            registers = device_def.get('registers', {}).get('read', [])
            if not registers:
                _LOGGER.error("No read registers found in configuration")
                return None

            # Optimize register reads
            optimized_groups = await self.optimizer.optimize_reads(registers)
            
            data = {}
            for group in optimized_groups:
                group_data = await self._read_register_group(group)
                data.update(group_data)

            duration = time.time() - start_time
            
            
            return data

        except Exception as e:
            error = handle_modbus_error(e)
            
            raise error

    async def _read_register_group(self, registers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Read a group of registers."""
        if not registers:
            return {}

        if self._shutdown:
            raise ModbusDeviceError("Device is shutting down")

        try:
            if not self.is_connected:
                await self.async_setup()

            data = {}
            for reg in registers:
                reg_count = reg.get('count', 1)
                reg_values = await self.proxy.read_registers(
                    reg['address'],
                    reg_count,
                    unit=reg.get('unit', self.slave)
                )
                data[reg['name']] = reg_values

            return data

        except Exception as e:
            self.is_connected = False
            raise handle_modbus_error(e)

    async def detect_firmware_version(self):
        """Detect firmware version from device."""
        try:
            # Lese Firmware-Version aus bekanntem Register
            fw_register = await self.read_register(self.FIRMWARE_VERSION_REGISTER)
            return self._parse_firmware_version(fw_register)
        except Exception as e:
            _LOGGER.warning("Could not detect firmware version: %s", e)
            return None

    async def update_register_definitions(self):
        """Update register definitions based on firmware version."""
        fw_version = await self.detect_firmware_version()
        if fw_version:
            # Lade passende Register-Definitionen
            new_definitions = self._load_firmware_specific_definitions(fw_version)
            if new_definitions:
                await self._apply_new_definitions(new_definitions)
                return True
        return False

    async def _apply_new_definitions(self, new_definitions):
        """Apply new register definitions and update entities."""
        # Entferne alte Entities
        await self.async_remove_old_entities()
        
        # Erstelle neue Entities mit aktualisierten Registern
        await self.async_setup_new_entities(new_definitions)

    async def setup_device(self) -> bool:
        """Set up the device with firmware detection and register setup."""
        try:
            # Detect firmware version
            if self.config.get("firmware_handling", {}).get("auto_detect", True):
                firmware_version = await self.detect_firmware_version()
                if firmware_version:
                    self.logger.info(f"Detected firmware version: {firmware_version}")
                    await self.update_register_definitions(firmware_version)
                else:
                    firmware_version = self.config["firmware_handling"]["fallback_version"]
                    self.logger.warning(f"Using fallback firmware version: {firmware_version}")
            
            # Setup common entities
            await self.setup_common_entities()
            
            # Setup device-specific entities
            await self.setup_device_entities()
            
            # Setup templates and helpers
            await self.setup_templates_and_helpers()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting up device: {e}")
            return False

    async def setup_common_entities(self):
        """Setup common entities from core/common_entities.yaml."""
        common_def = self.load_common_definition()
        if not common_def:
            return
        
        for entity_type, entities in common_def.get("common_entities", {}).items():
            for entity in entities:
                await self.async_add_entity(entity_type, entity)

    async def setup_templates_and_helpers(self):
        """Setup templates and helper entities."""
        device_def = self.get_device_definition(self.device_type)
        if not device_def:
            return
        
        # Setup energy monitoring templates
        if device_def.get("supports_energy_monitoring", False):
            await self.setup_energy_templates()
        
        # Setup cost calculation templates
        if device_def.get("supports_cost_calculation", False):
            await self.setup_cost_templates()