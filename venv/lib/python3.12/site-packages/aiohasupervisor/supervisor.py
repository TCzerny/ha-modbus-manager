"""Supervisor client for supervisor."""

from aiohttp import ClientTimeout

from .client import _SupervisorComponentClient
from .const import ResponseType
from .models.supervisor import (
    SupervisorInfo,
    SupervisorOptions,
    SupervisorStats,
    SupervisorUpdateOptions,
)


class SupervisorManagementClient(_SupervisorComponentClient):
    """Handles supervisor access in supervisor."""

    async def ping(self) -> None:
        """Check connection to supervisor."""
        await self._client.get(
            "supervisor/ping",
            response_type=ResponseType.NONE,
            timeout=ClientTimeout(total=15),
        )

    async def info(self) -> SupervisorInfo:
        """Get supervisor info."""
        result = await self._client.get("supervisor/info")
        return SupervisorInfo.from_dict(result.data)

    async def stats(self) -> SupervisorStats:
        """Get supervisor stats."""
        result = await self._client.get("supervisor/stats")
        return SupervisorStats.from_dict(result.data)

    async def update(self, options: SupervisorUpdateOptions | None = None) -> None:
        """Update supervisor.

        Providing a target version in options only works on development systems.
        On non-development systems this API will always update supervisor to the
        latest version and ignore that field.
        """
        await self._client.post(
            "supervisor/update",
            json=options.to_dict() if options else None,
            timeout=None,
        )

    async def reload(self) -> None:
        """Reload supervisor (add-ons, configuration, etc)."""
        await self._client.post("supervisor/reload")

    async def restart(self) -> None:
        """Restart supervisor."""
        await self._client.post("supervisor/restart")

    async def set_options(self, options: SupervisorOptions) -> None:
        """Set supervisor options."""
        await self._client.post("supervisor/options", json=options.to_dict())

    async def repair(self) -> None:
        """Repair local supervisor and docker setup."""
        await self._client.post("supervisor/repair")
