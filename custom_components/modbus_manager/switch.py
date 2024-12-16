"""Modbus Manager Switch Platform."""
from datetime import timedelta
from typing import Any, Dict, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .modbus_hub import ModbusManagerHub
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Richte die Modbus Manager Switches ein."""
    _LOGGER.debug(
        "Switch Setup wird ausgeführt",
        extra={
            "entry_id": entry.entry_id
        }
    )

    # Prüfe ob die Domain existiert
    if DOMAIN not in hass.data:
        _LOGGER.error(
            "Domain nicht in hass.data gefunden",
            extra={
                "entry_id": entry.entry_id
            }
        )
        return False

    # Prüfe ob der Hub existiert
    if entry.entry_id not in hass.data[DOMAIN]:
        _LOGGER.error(
            "Hub nicht gefunden",
            extra={
                "entry_id": entry.entry_id
            }
        )
        return False

    hub: ModbusManagerHub = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.debug(
        "Hub gefunden",
        extra={
            "entry_id": entry.entry_id,
            "hub_name": hub.name
        }
    )

    try:
        # Hole die Gerätedefinition
        device_def = await hub.get_device_definition(hub.device_type)
        if not device_def:
            _LOGGER.error(
                "Keine Gerätekonfiguration gefunden",
                extra={
                    "entry_id": entry.entry_id,
                    "device_type": hub.device_type
                }
            )
            return False

        _LOGGER.debug(
            "Gerätekonfiguration geladen",
            extra={
                "entry_id": entry.entry_id,
                "device_type": hub.device_type
            }
        )
        
        # Erstelle die Switches
        switches = []
        write_registers = device_def.get('registers', {}).get('write', [])
        polling_config = device_def.get('polling', {})
        
        _LOGGER.info(
            "Erstelle Switches",
            extra={
                "entry_id": entry.entry_id,
                "switch_count": len(write_registers)
            }
        )

        # Erstelle einen Coordinator für jede Polling-Gruppe
        for group_name, group_config in polling_config.items():
            interval = group_config.get('interval', 30)
            registers = group_config.get('registers', [])
            
            if not registers:
                continue
                
            coordinator = DataUpdateCoordinator(
                hass,
                _LOGGER,
                name=f"{hub.name}_{group_name}",
                update_method=lambda: hub.read_registers(hub.device_type),
                update_interval=timedelta(seconds=interval),
            )
            
            # Speichere den Coordinator im Hub
            if hub.device_type not in hub.coordinators:
                hub.coordinators[hub.device_type] = {}
            hub.coordinators[hub.device_type][group_name] = coordinator
            
            _LOGGER.debug(
                "Coordinator erstellt",
                extra={
                    "entry_id": entry.entry_id,
                    "group": group_name,
                    "interval": interval
                }
            )
            
            # Erstelle Switches für diese Gruppe
            for reg_name in registers:
                reg_def = next((r for r in write_registers if r['name'] == reg_name), None)
                if reg_def:
                    try:
                        switch = ModbusSwitch(
                            hub=hub,
                            coordinator=coordinator,
                            name=reg_name,
                            device_def=reg_def,
                            polling_group=group_name
                        )
                        switches.append(switch)
                        _LOGGER.debug(
                            "Switch erstellt",
                            extra={
                                "entry_id": entry.entry_id,
                                "name": reg_name,
                                "group": group_name
                            }
                        )
                    except Exception as e:
                        _LOGGER.error(
                            "Fehler beim Erstellen des Switch",
                            extra={
                                "entry_id": entry.entry_id,
                                "name": reg_name,
                                "error": str(e)
                            }
                        )

        if switches:
            async_add_entities(switches)
            _LOGGER.info(
                "Switches erfolgreich hinzugefügt",
                extra={
                    "entry_id": entry.entry_id,
                    "count": len(switches)
                }
            )
            return True

        return False

    except Exception as e:
        _LOGGER.error(
            "Fehler beim Setup der Switches",
            extra={
                "entry_id": entry.entry_id,
                "error": str(e)
            }
        )
        return False

class ModbusSwitch(CoordinatorEntity, SwitchEntity):
    """Modbus Manager Switch Klasse."""

    def __init__(
        self,
        hub: ModbusManagerHub,
        coordinator: DataUpdateCoordinator,
        name: str,
        device_def: dict,
        polling_group: str,
    ):
        """Initialisiere den Switch."""
        super().__init__(coordinator)
        
        self._hub = hub
        self._name = name
        self._device_def = device_def
        self._polling_group = polling_group
        self._state = False
        
        # Setze die Switch-Attribute
        self._attr_name = f"{hub.name} {name}"
        self._attr_unique_id = f"{hub.name}_{name}"
        
        # Setze die Geräte-Info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hub.name)},
            name=hub.name,
            manufacturer=device_def.get("manufacturer", "Unknown"),
            model=hub.device_type,
        )
        
        _LOGGER.debug(
            f"Switch initialisiert: {self._name} "
            f"(ID: {self._attr_unique_id}, "
            f"Polling-Gruppe: {self._polling_group})"
        )

    @property
    def is_on(self) -> bool:
        """Gib den aktuellen Zustand des Switch zurück."""
        if not self.coordinator.data:
            return False
            
        try:
            # Hole die Rohdaten für diesen Switch
            raw_value = self.coordinator.data.get(self._name)
            if raw_value is None:
                return False
                
            return bool(raw_value[0])
            
        except Exception as e:
            _LOGGER.error(
                "Fehler beim Verarbeiten des Switch-Werts",
                extra={
                    "name": self._name,
                    "error": str(e)
                }
            )
            return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Schalte den Switch ein."""
        await self._write_register(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Schalte den Switch aus."""
        await self._write_register(False)

    async def _write_register(self, value: bool) -> None:
        """Schreibe einen Wert in das Register."""
        try:
            address = self._device_def.get("address")
            reg_type = self._device_def.get("type", "uint16")
            scale = self._device_def.get("scale", 1)
            swap = self._device_def.get("swap")

            # Konvertiere den booleschen Wert in den entsprechenden Zahlenwert
            write_value = 1 if value else 0

            # Schreibe den Wert über den Hub
            success = await self._hub.write_register(
                self._hub.name,
                address,
                write_value,
                reg_type,
                scale,
                swap
            )

            if success:
                _LOGGER.debug(
                    "Switch-Wert geschrieben",
                    extra={
                        "name": self._name,
                        "value": value
                    }
                )
                self._state = value
                self.async_write_ha_state()
            else:
                _LOGGER.error(
                    "Fehler beim Schreiben des Switch-Werts",
                    extra={
                        "name": self._name,
                        "value": value
                    }
                )

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Schreiben des Switch-Werts",
                extra={
                    "name": self._name,
                    "error": str(e)
                }
            ) 