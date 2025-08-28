"""Models for supervisor network."""

from abc import ABC
from dataclasses import dataclass
from enum import StrEnum
from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    IPv6Address,
    IPv6Interface,
)

from .base import Options, Request, ResponseData

# --- ENUMS ----


class InterfaceType(StrEnum):
    """InterfaceType type."""

    ETHERNET = "ethernet"
    WIRELESS = "wireless"
    VLAN = "vlan"


class InterfaceMethod(StrEnum):
    """InterfaceMethod type."""

    DISABLED = "disabled"
    STATIC = "static"
    AUTO = "auto"


class WifiMode(StrEnum):
    """WifiMode type."""

    INFRASTRUCTURE = "infrastructure"
    MESH = "mesh"
    ADHOC = "adhoc"
    AP = "ap"


class AuthMethod(StrEnum):
    """AuthMethod type."""

    OPEN = "open"
    WEP = "wep"
    WPA_PSK = "wpa-psk"


# --- OBJECTS ----


@dataclass(frozen=True)
class IpBase(ABC):
    """IpBase ABC type."""

    method: InterfaceMethod
    ready: bool | None


@dataclass(frozen=True, slots=True)
class IPv4(IpBase, ResponseData):
    """IPv4 model."""

    address: list[IPv4Interface]
    nameservers: list[IPv4Address]
    gateway: IPv4Address | None


@dataclass(frozen=True, slots=True)
class IPv6(IpBase, ResponseData):
    """IPv6 model."""

    address: list[IPv6Interface]
    nameservers: list[IPv6Address]
    gateway: IPv6Address | None


@dataclass(frozen=True, slots=True)
class Wifi(ResponseData):
    """Wifi model."""

    mode: WifiMode
    auth: AuthMethod
    ssid: str
    signal: int | None


@dataclass(frozen=True, slots=True)
class Vlan(ResponseData):
    """Vlan model."""

    id: int
    interface: str


@dataclass(frozen=True, slots=True)
class NetworkInterface(ResponseData):
    """NetworkInterface model."""

    interface: str
    type: InterfaceType
    enabled: bool
    connected: bool
    primary: bool
    mac: str
    ipv4: IPv4
    ipv6: IPv6
    wifi: Wifi | None
    vlan: Vlan | None


@dataclass(frozen=True, slots=True)
class DockerNetwork(ResponseData):
    """DockerNetwork model."""

    interface: str
    address: IPv4Network
    gateway: IPv4Address
    dns: IPv4Address


@dataclass(frozen=True, slots=True)
class NetworkInfo(ResponseData):
    """NetworkInfo model."""

    interfaces: list[NetworkInterface]
    docker: DockerNetwork
    host_internet: bool | None
    supervisor_internet: bool


@dataclass(frozen=True, slots=True)
class IPv4Config(Request):
    """IPv4Config model."""

    address: list[IPv4Interface] | None = None
    method: InterfaceMethod | None = None
    gateway: IPv4Address | None = None
    nameservers: list[IPv4Address] | None = None


@dataclass(frozen=True, slots=True)
class IPv6Config(Request):
    """IPv6Config model."""

    address: list[IPv6Interface] | None = None
    method: InterfaceMethod | None = None
    gateway: IPv6Address | None = None
    nameservers: list[IPv6Address] | None = None


@dataclass(frozen=True, slots=True)
class WifiConfig(Request):
    """WifiConfig model."""

    mode: WifiMode | None = None
    method: AuthMethod | None = None
    ssid: str | None = None
    psk: str | None = None


@dataclass(frozen=True, slots=True)
class NetworkInterfaceConfig(Options):
    """NetworkInterfaceConfig model."""

    ipv4: IPv4Config | None = None
    ipv6: IPv6Config | None = None
    wifi: WifiConfig | None = None
    enabled: bool | None = None


@dataclass(frozen=True, slots=True)
class AccessPoint(ResponseData):
    """AccessPoint model."""

    mode: WifiMode
    ssid: str
    frequency: int
    signal: int
    mac: str


@dataclass(frozen=True, slots=True)
class AccessPointList(ResponseData):
    """AccessPointList model."""

    accesspoints: list[AccessPoint]


@dataclass(frozen=True, slots=True)
class VlanConfig(Options):
    """VlanConfig model."""

    ipv4: IPv4Config | None = None
    ipv6: IPv6Config | None = None
