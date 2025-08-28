"""Mounts client for Supervisor."""

from .client import _SupervisorComponentClient
from .models.mounts import CIFSMountRequest, MountsInfo, MountsOptions, NFSMountRequest


class MountsClient(_SupervisorComponentClient):
    """Handle mounts access in supervisor."""

    async def info(self) -> MountsInfo:
        """Get mounts info."""
        result = await self._client.get("mounts")
        return MountsInfo.from_dict(result.data)

    async def options(self, options: MountsOptions) -> None:
        """Set mounts options."""
        await self._client.post("mounts/options", json=options.to_dict())

    async def create_mount(
        self, name: str, config: CIFSMountRequest | NFSMountRequest
    ) -> None:
        """Create a new mount."""
        await self._client.post("mounts", json={"name": name, **config.to_dict()})

    async def update_mount(
        self, name: str, config: CIFSMountRequest | NFSMountRequest
    ) -> None:
        """Update an existing mount."""
        await self._client.put(f"mounts/{name}", json=config.to_dict())

    async def delete_mount(self, name: str) -> None:
        """Delete an existing mount."""
        await self._client.delete(f"mounts/{name}")

    async def reload_mount(self, name: str) -> None:
        """Reload details of an existing mount."""
        await self._client.post(f"mounts/{name}/reload")
