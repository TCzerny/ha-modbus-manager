"""Models for Home Assistant."""

from dataclasses import dataclass
from ipaddress import IPv4Address

from .base import DEFAULT, ContainerStats, Options, Request, ResponseData

# --- OBJECTS ----


@dataclass(frozen=True, slots=True)
class HomeAssistantInfo(ResponseData):
    """HomeAssistantInfo model."""

    version: str | None
    version_latest: str | None
    update_available: bool
    machine: str
    ip_address: IPv4Address
    arch: str
    image: str
    boot: bool
    port: int
    ssl: bool
    watchdog: bool
    audio_input: str
    audio_output: str
    backups_exclude_database: bool


@dataclass(frozen=True, slots=True)
class HomeAssistantStats(ContainerStats):
    """HomeAssistantStats model."""


@dataclass(frozen=True, slots=True)
class HomeAssistantOptions(Options):
    """HomeAssistantOptions model."""

    boot: bool | None = None
    image: str | None = DEFAULT  # type: ignore[assignment]
    port: int | None = None
    ssl: bool | None = None
    watchdog: bool | None = None
    refresh_token: str | None = DEFAULT  # type: ignore[assignment]
    audio_input: str | None = DEFAULT  # type: ignore[assignment]
    audio_output: str | None = DEFAULT  # type: ignore[assignment]
    backups_exclude_database: bool | None = None


@dataclass(frozen=True, slots=True)
class HomeAssistantUpdateOptions(Options):
    """HomeAssistantUpdateOptions model."""

    version: str | None = None
    backup: bool | None = None


@dataclass(frozen=True, slots=True)
class HomeAssistantRestartOptions(Options):
    """HomeAssistantRestartOptions model."""

    safe_mode: bool | None = None
    force: bool | None = None


@dataclass(frozen=True, slots=True)
class HomeAssistantRebuildOptions(Options):
    """HomeAssistantRebuildOptions model."""

    safe_mode: bool | None = None
    force: bool | None = None


@dataclass(frozen=True, slots=True)
class HomeAssistantStopOptions(Request):
    """HomeAssistantStopOptions model."""

    force: bool
