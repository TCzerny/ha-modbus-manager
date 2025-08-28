"""Models for host APIs."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .base import Request, ResponseData
from .root import HostFeature

# --- ENUMS ----


class ServiceState(StrEnum):
    """ServiceState type.

    The service state is determined by systemd, not supervisor. The list below
    is pulled from `systemctl --state=help`. It may be incomplete and it may
    change based on the host. Therefore within a list of services there may be
    some with a state not in this list parsed as string. If you find this
    please create an issue or pr to get the state added.
    """

    ACTIVE = "active"
    RELOADING = "reloading"
    INACTIVE = "inactive"
    FAILED = "failed"
    ACTIVATING = "activating"
    DEACTIVATING = "deactivating"
    MAINTENANCE = "maintenance"


# --- OBJECTS ----


@dataclass(frozen=True, slots=True)
class HostInfo(ResponseData):
    """HostInfo model."""

    agent_version: str | None
    apparmor_version: str | None
    chassis: str | None
    virtualization: str | None
    cpe: str | None
    deployment: str | None
    disk_free: float
    disk_total: float
    disk_used: float
    disk_life_time: float
    features: list[HostFeature]
    hostname: str | None
    llmnr_hostname: str | None
    kernel: str | None
    operating_system: str | None
    timezone: str | None
    dt_utc: datetime | None
    dt_synchronized: bool | None
    use_ntp: bool | None
    startup_time: float | None
    boot_timestamp: int | None
    broadcast_llmnr: bool | None
    broadcast_mdns: bool | None


@dataclass(frozen=True, slots=True)
class ShutdownOptions(Request):
    """ShutdownOptions model."""

    force: bool


@dataclass(frozen=True, slots=True)
class RebootOptions(Request):
    """RebootOptions model."""

    force: bool


@dataclass(frozen=True, slots=True)
class HostOptions(Request):
    """HostOptions model."""

    hostname: str


@dataclass(frozen=True, slots=True)
class Service(ResponseData):
    """Service model."""

    name: str
    description: str
    state: ServiceState | str


@dataclass(frozen=True, slots=True)
class ServiceList(ResponseData):
    """ServiceList model."""

    services: list[Service]
