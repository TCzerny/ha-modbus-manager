"""Models for OS APIs."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePath

from .base import Options, Request, ResponseData

# --- ENUMS ----


class RaucState(StrEnum):
    """RaucState type."""

    GOOD = "good"
    BAD = "bad"
    ACTIVE = "active"


class BootSlotName(StrEnum):
    """BootSlotName type."""

    A = "A"
    B = "B"


# --- OBJECTS ----


@dataclass(frozen=True, slots=True)
class BootSlot(ResponseData):
    """BootSlot model."""

    state: str
    status: RaucState | None
    version: str | None


@dataclass(frozen=True, slots=True)
class OSInfo(ResponseData):
    """OSInfo model."""

    version: str | None
    version_latest: str | None
    update_available: bool
    board: str | None
    boot: str | None
    data_disk: str | None
    boot_slots: dict[str, BootSlot]


@dataclass(frozen=True, slots=True)
class OSUpdate(Request):
    """OSUpdate model."""

    version: str | None = None


@dataclass(frozen=True, slots=True)
class MigrateDataOptions(Request):
    """MigrateDataOptions model."""

    device: str


@dataclass(frozen=True, slots=True)
class DataDisk(ResponseData):
    """DataDisk model."""

    name: str
    vendor: str
    model: str
    serial: str
    size: int
    id: str
    dev_path: PurePath


@dataclass(frozen=True, slots=True)
class DataDiskList(ResponseData):
    """DataDiskList model."""

    disks: list[DataDisk]


@dataclass(frozen=True, slots=True)
class SetBootSlotOptions(Request):
    """SetBootSlotOptions model."""

    boot_slot: BootSlotName


@dataclass(frozen=True, slots=True)
class GreenInfo(ResponseData):
    """GreenInfo model."""

    activity_led: bool
    power_led: bool
    system_health_led: bool


@dataclass(frozen=True, slots=True)
class GreenOptions(Options):
    """GreenOptions model."""

    activity_led: bool | None = None
    power_led: bool | None = None
    system_health_led: bool | None = None


@dataclass(frozen=True, slots=True)
class YellowInfo(ResponseData):
    """YellowInfo model."""

    disk_led: bool
    heartbeat_led: bool
    power_led: bool


@dataclass(frozen=True, slots=True)
class YellowOptions(Options):
    """YellowOptions model."""

    disk_led: bool | None = None
    heartbeat_led: bool | None = None
    power_led: bool | None = None
