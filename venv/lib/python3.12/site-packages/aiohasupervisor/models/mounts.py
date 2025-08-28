"""Models for Supervisor mounts."""

from abc import ABC
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePath
from typing import Literal

from .base import Request, ResponseData

# --- ENUMS ----


class MountType(StrEnum):
    """MountType type."""

    CIFS = "cifs"
    NFS = "nfs"


class MountUsage(StrEnum):
    """MountUsage type."""

    BACKUP = "backup"
    MEDIA = "media"
    SHARE = "share"


class MountState(StrEnum):
    """MountState type."""

    ACTIVE = "active"
    ACTIVATING = "activating"
    DEACTIVATING = "deactivating"
    FAILED = "failed"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    RELOADING = "reloading"


class MountCifsVersion(StrEnum):
    """Mount CIFS version."""

    LEGACY_1_0 = "1.0"
    LEGACY_2_0 = "2.0"


# --- OBJECTS ----


@dataclass(frozen=True)
class Mount(ABC):
    """Mount ABC type."""

    usage: MountUsage
    server: str
    port: int | None = field(kw_only=True, default=None)


@dataclass(frozen=True)
class CIFSMount(ABC):
    """CIFSMount ABC type."""

    share: str
    version: MountCifsVersion | None = field(kw_only=True, default=None)


@dataclass(frozen=True)
class NFSMount(ABC):
    """NFSMount ABC type."""

    path: PurePath


@dataclass(frozen=True)
class MountResponse(ABC):
    """MountResponse model."""

    name: str
    read_only: bool
    state: MountState | None
    user_path: PurePath | None


@dataclass(frozen=True)
class MountRequest(ABC):  # noqa: B024
    """MountRequest model."""

    read_only: bool | None = field(kw_only=True, default=None)


@dataclass(frozen=True, slots=True)
class CIFSMountResponse(Mount, MountResponse, CIFSMount, ResponseData):
    """CIFSMountResponse model."""

    type: Literal[MountType.CIFS]


@dataclass(frozen=True, slots=True)
class NFSMountResponse(Mount, MountResponse, NFSMount, ResponseData):
    """NFSMountResponse model."""

    type: Literal[MountType.NFS]


@dataclass(frozen=True, slots=True)
class CIFSMountRequest(Mount, MountRequest, CIFSMount, Request):
    """CIFSMountRequest model."""

    type: Literal[MountType.CIFS] = field(init=False, default=MountType.CIFS)
    username: str | None = field(kw_only=True, default=None)
    password: str | None = field(kw_only=True, default=None)


@dataclass(frozen=True, slots=True)
class NFSMountRequest(Mount, MountRequest, NFSMount, Request):
    """NFSMountRequest model."""

    type: Literal[MountType.NFS] = field(init=False, default=MountType.NFS)


@dataclass(frozen=True, slots=True)
class MountsInfo(ResponseData):
    """MountsInfo model."""

    default_backup_mount: str | None
    mounts: list[CIFSMountResponse | NFSMountResponse]


@dataclass(frozen=True, slots=True)
class MountsOptions(Request):
    """MountsOptions model."""

    default_backup_mount: str | None
