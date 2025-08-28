"""Host client for supervisor."""

from .client import _SupervisorComponentClient
from .const import TIMEOUT_60_SECONDS
from .models.host import (
    HostInfo,
    HostOptions,
    RebootOptions,
    Service,
    ServiceList,
    ShutdownOptions,
)


class HostClient(_SupervisorComponentClient):
    """Handles host access in supervisor."""

    async def info(self) -> HostInfo:
        """Get host info."""
        result = await self._client.get("host/info")
        return HostInfo.from_dict(result.data)

    async def reboot(self, options: RebootOptions | None = None) -> None:
        """Reboot host."""
        await self._client.post(
            "host/reboot",
            json=options.to_dict() if options else None,
            timeout=TIMEOUT_60_SECONDS,
        )

    async def shutdown(self, options: ShutdownOptions | None = None) -> None:
        """Shutdown host."""
        await self._client.post(
            "host/shutdown", json=options.to_dict() if options else None
        )

    async def reload(self) -> None:
        """Reload host info cache."""
        await self._client.post("host/reload")

    async def set_options(self, options: HostOptions) -> None:
        """Set host options."""
        await self._client.post("host/options", json=options.to_dict())

    async def services(self) -> list[Service]:
        """Get list of available services on host."""
        result = await self._client.get("host/services")
        return ServiceList.from_dict(result.data).services

    # Omitted for now - Log endpoints
