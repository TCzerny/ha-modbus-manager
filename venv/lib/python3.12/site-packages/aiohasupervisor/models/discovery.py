"""Models for discovery component."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from .base import Request, ResponseData


@dataclass(frozen=True, slots=True)
class DiscoveryConfig(Request):
    """DiscoveryConfig model."""

    service: str
    config: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Discovery(ResponseData):
    """Discovery model."""

    addon: str
    service: str
    uuid: UUID
    config: dict[str, Any]


@dataclass(frozen=True, slots=True)
class DiscoveryList(ResponseData):
    """DiscoveryList model."""

    discovery: list[Discovery]


@dataclass(frozen=True, slots=True)
class SetDiscovery(ResponseData):
    """SetDiscovery model."""

    uuid: UUID
