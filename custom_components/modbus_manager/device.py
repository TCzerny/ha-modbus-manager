class ModbusManagerDevice:
    def __init__(self, hass, config_entry):
        # ...
        self.logger = ModbusManagerLogger(f"device_{self.name}")
        # ...

    async def async_update_ha_state(self):
        """Update Home Assistant state."""
        if self._config.get("firmware_handling", {}).get("auto_detect", False):
            current_version = await self.detect_firmware_version()
            if current_version != self._current_firmware_version:
                self.logger.info(f"Firmware version changed from {self._current_firmware_version} to {current_version}")
                await self.update_register_definitions(current_version)
                self._current_firmware_version = current_version

        await super().async_update_ha_state() 