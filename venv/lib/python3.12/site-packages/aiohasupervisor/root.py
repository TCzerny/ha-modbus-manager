"""Main client for supervisor."""

from typing import Self

from aiohttp import ClientSession, ClientTimeout

from .addons import AddonsClient
from .backups import BackupsClient
from .client import _SupervisorClient
from .discovery import DiscoveryClient
from .homeassistant import HomeAssistantClient
from .host import HostClient
from .models.root import AvailableUpdate, AvailableUpdates, RootInfo
from .mounts import MountsClient
from .network import NetworkClient
from .os import OSClient
from .resolution import ResolutionClient
from .store import StoreClient
from .supervisor import SupervisorManagementClient


class SupervisorClient:
    """Main supervisor client for all Supervisor access."""

    def __init__(
        self,
        api_host: str,
        token: str,
        session: ClientSession | None = None,
    ) -> None:
        """Initialize client."""
        self._client = _SupervisorClient(api_host, token, session)
        self._addons = AddonsClient(self._client)
        self._os = OSClient(self._client)
        self._backups = BackupsClient(self._client)
        self._discovery = DiscoveryClient(self._client)
        self._mounts = MountsClient(self._client)
        self._network = NetworkClient(self._client)
        self._host = HostClient(self._client)
        self._resolution = ResolutionClient(self._client)
        self._store = StoreClient(self._client)
        self._supervisor = SupervisorManagementClient(self._client)
        self._homeassistant = HomeAssistantClient(self._client)

    @property
    def addons(self) -> AddonsClient:
        """Get addons component client."""
        return self._addons

    @property
    def homeassistant(self) -> HomeAssistantClient:
        """Get Home Assistant component client."""
        return self._homeassistant

    @property
    def os(self) -> OSClient:
        """Get OS component client."""
        return self._os

    @property
    def backups(self) -> BackupsClient:
        """Get backups component client."""
        return self._backups

    @property
    def discovery(self) -> DiscoveryClient:
        """Get discovery component client."""
        return self._discovery

    @property
    def mounts(self) -> MountsClient:
        """Get mounts component client."""
        return self._mounts

    @property
    def network(self) -> NetworkClient:
        """Get network component client."""
        return self._network

    @property
    def host(self) -> HostClient:
        """Get host component client."""
        return self._host

    @property
    def resolution(self) -> ResolutionClient:
        """Get resolution center component client."""
        return self._resolution

    @property
    def store(self) -> StoreClient:
        """Get store component client."""
        return self._store

    @property
    def supervisor(self) -> SupervisorManagementClient:
        """Get supervisor component client."""
        return self._supervisor

    async def info(self) -> RootInfo:
        """Get root info."""
        result = await self._client.get("info")
        return RootInfo.from_dict(result.data)

    async def refresh_updates(self) -> None:
        """Refresh updates."""
        await self._client.post("refresh_updates", timeout=ClientTimeout(total=300))

    async def available_updates(self) -> list[AvailableUpdate]:
        """Get available updates."""
        result = await self._client.get("available_updates")
        return AvailableUpdates.from_dict(result.data).available_updates

    async def close(self) -> None:
        """Close open client session."""
        await self._client.close()

    async def __aenter__(self) -> Self:
        """Async enter, closes session on exit."""
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Close session."""
        await self.close()
