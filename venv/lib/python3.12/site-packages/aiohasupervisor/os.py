"""OS client for supervisor."""

from .client import _SupervisorComponentClient
from .models.os import (
    DataDisk,
    DataDiskList,
    GreenInfo,
    GreenOptions,
    MigrateDataOptions,
    OSInfo,
    OSUpdate,
    SetBootSlotOptions,
    YellowInfo,
    YellowOptions,
)


class OSClient(_SupervisorComponentClient):
    """Handles OS access in supervisor."""

    async def info(self) -> OSInfo:
        """Get OS info."""
        result = await self._client.get("os/info")
        return OSInfo.from_dict(result.data)

    async def update(self, options: OSUpdate | None = None) -> None:
        """Update OS."""
        await self._client.post(
            "os/update", json=options.to_dict() if options else None, timeout=None
        )

    async def config_sync(self) -> None:
        """Trigger config reload on OS."""
        await self._client.post("os/config/sync")

    async def migrate_data(self, options: MigrateDataOptions) -> None:
        """Migrate data to new data disk and reboot."""
        await self._client.post("os/datadisk/move", json=options.to_dict())

    async def list_data_disks(self) -> list[DataDisk]:
        """Get all data disks."""
        result = await self._client.get("os/datadisk/list")
        return DataDiskList.from_dict(result.data).disks

    async def wipe_data(self) -> None:
        """Trigger data disk wipe on host and reboot."""
        await self._client.post("os/datadisk/wipe")

    async def set_boot_slot(self, options: SetBootSlotOptions) -> None:
        """Change active boot slot on host and reboot."""
        await self._client.post("os/boot-slot", json=options.to_dict())

    async def green_info(self) -> GreenInfo:
        """Get info for green board (if in use)."""
        result = await self._client.get("os/boards/green")
        return GreenInfo.from_dict(result.data)

    async def set_green_options(self, options: GreenOptions) -> None:
        """Set options for green board (if in use)."""
        await self._client.post("os/boards/green", json=options.to_dict())

    async def yellow_info(self) -> YellowInfo:
        """Get info for yellow board (if in use)."""
        result = await self._client.get("os/boards/yellow")
        return YellowInfo.from_dict(result.data)

    async def set_yellow_options(self, options: YellowOptions) -> None:
        """Set options for yellow board (if in use)."""
        await self._client.post("os/boards/yellow", json=options.to_dict())
