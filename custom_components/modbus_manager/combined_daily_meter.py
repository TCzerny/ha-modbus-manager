"""Persistent daily energy counters for combined inverter+iHM devices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .logger import ModbusManagerLogger

_LOGGER = ModbusManagerLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.combined_daily_meters"


@dataclass
class _MeterState:
    """Runtime state for one cumulative energy source."""

    day: str
    last_total: float | None
    daily: float
    source_unique_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "last_total": self.last_total,
            "daily": self.daily,
            "source_unique_id": self.source_unique_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> _MeterState:
        if not isinstance(data, dict):
            return cls(day="", last_total=None, daily=0.0)
        day = str(data.get("day", ""))
        last_total = data.get("last_total")
        daily_raw = data.get("daily", 0.0)
        try:
            daily = float(daily_raw)
        except (TypeError, ValueError):
            daily = 0.0
        if last_total is not None:
            try:
                last_total = float(last_total)
            except (TypeError, ValueError):
                last_total = None
        source_unique_id = data.get("source_unique_id")
        return cls(
            day=day,
            last_total=last_total,
            daily=daily,
            source_unique_id=(
                str(source_unique_id) if source_unique_id is not None else None
            ),
        )


class _DailyEnergyMeter:
    """Accumulate daily energy from a monotonic total-increasing source."""

    def __init__(self, meter_id: str) -> None:
        self._meter_id = meter_id
        self._state = _MeterState(day="", last_total=None, daily=0.0)

    @property
    def daily_value(self) -> float:
        """Current daily accumulated value."""
        return self._state.daily

    @property
    def source_unique_id(self) -> str | None:
        return self._state.source_unique_id

    @property
    def current_day(self) -> str:
        """Local calendar day (ISO) for the active accumulation period."""
        return self._state.day

    def load(self, saved: dict[str, Any] | None) -> None:
        """Restore persisted meter state."""
        self._state = _MeterState.from_dict(saved)

    def export(self) -> dict[str, Any]:
        """Serialize meter state for persistence."""
        return self._state.to_dict()

    def update(
        self,
        total: float,
        now: datetime,
        source_unique_id: str | None = None,
    ) -> float:
        """Update daily accumulation from a cumulative total reading."""
        local_now = dt_util.as_local(now)
        current_day = local_now.date().isoformat()

        if source_unique_id:
            self._state.source_unique_id = source_unique_id

        if self._state.day != current_day:
            self._state.day = current_day
            self._state.daily = 0.0
            self._state.last_total = total
            return self._state.daily

        if self._state.last_total is None:
            self._state.last_total = total
            return self._state.daily

        if total < self._state.last_total:
            # Source counter reset (meter replacement / rollover).
            self._state.daily += total
        else:
            self._state.daily += total - self._state.last_total

        self._state.last_total = total
        return self._state.daily


class CombinedDailyMeterPair:
    """Import/export daily meters for one combined config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._hass = hass
        self._entry_id = entry_id
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._import_meter = _DailyEnergyMeter("import")
        self._export_meter = _DailyEnergyMeter("export")
        self._loaded = False
        self._dirty = False

    async def async_load(self) -> None:
        """Load persisted counters for this combined entry."""
        if self._loaded:
            return
        stored = await self._store.async_load() or {}
        entries = stored.get("entries", {})
        entry_state = entries.get(self._entry_id, {})
        if isinstance(entry_state, dict):
            self._import_meter.load(entry_state.get("import"))
            self._export_meter.load(entry_state.get("export"))
        self._loaded = True

    @callback
    def async_schedule_save(self) -> None:
        """Persist counters when state changed."""
        if not self._dirty:
            return
        self._dirty = False
        self._hass.async_create_task(self._async_save())

    async def _async_save(self) -> None:
        stored = await self._store.async_load() or {}
        entries = stored.get("entries", {})
        if not isinstance(entries, dict):
            entries = {}
        entries[self._entry_id] = {
            "import": self._import_meter.export(),
            "export": self._export_meter.export(),
        }
        await self._store.async_save({"entries": entries})

    async def async_remove_entry(self) -> None:
        """Remove persisted state for this combined entry."""
        stored = await self._store.async_load() or {}
        entries = stored.get("entries", {})
        if isinstance(entries, dict) and self._entry_id in entries:
            entries = dict(entries)
            del entries[self._entry_id]
            await self._store.async_save({"entries": entries})

    def update(
        self,
        import_total: float | None,
        export_total: float | None,
        now: datetime | None = None,
        import_unique_id: str | None = None,
        export_unique_id: str | None = None,
    ) -> dict[str, float | None]:
        """Update both meters and return current daily values."""
        timestamp = now or dt_util.now()
        import_daily: float | None = None
        export_daily: float | None = None

        if import_total is not None:
            import_daily = self._import_meter.update(
                import_total, timestamp, import_unique_id
            )
            self._dirty = True
        if export_total is not None:
            export_daily = self._export_meter.update(
                export_total, timestamp, export_unique_id
            )
            self._dirty = True

        if self._dirty:
            self.async_schedule_save()

        return {
            "import": import_daily,
            "export": export_daily,
        }

    def metadata(self, meter_key: str) -> dict[str, Any]:
        """Return sensor metadata for one daily meter."""
        meter = (
            self._import_meter
            if meter_key == "import"
            else self._export_meter
            if meter_key == "export"
            else None
        )
        if meter is None:
            return {}
        return {
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "total",
            "precision": 3,
            "aggregation": "daily_meter",
            "source_unique_id": meter.source_unique_id,
            "meter_day": meter.current_day,
        }
