"""Discovery client for supervisor."""

from uuid import UUID

from .client import _SupervisorComponentClient
from .const import TIMEOUT_60_SECONDS, ResponseType
from .models.discovery import Discovery, DiscoveryConfig, DiscoveryList, SetDiscovery


class DiscoveryClient(_SupervisorComponentClient):
    """Handles discovery access in supervisor."""

    async def list(self) -> list[Discovery]:
        """List discovered active services."""
        result = await self._client.get("discovery", timeout=TIMEOUT_60_SECONDS)
        return DiscoveryList.from_dict(result.data).discovery

    async def get(self, uuid: UUID) -> Discovery:
        """Get discovery details for a service."""
        result = await self._client.get(f"discovery/{uuid.hex}")
        return Discovery.from_dict(result.data)

    async def delete(self, uuid: UUID) -> None:
        """Remove discovery for a service."""
        await self._client.delete(f"discovery/{uuid.hex}")

    async def set(self, config: DiscoveryConfig) -> UUID:
        """Inform supervisor of an available service."""
        result = await self._client.post(
            "discovery", json=config.to_dict(), response_type=ResponseType.JSON
        )
        return SetDiscovery.from_dict(result.data).uuid
