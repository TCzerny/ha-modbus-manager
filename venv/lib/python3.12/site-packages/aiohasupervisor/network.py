"""Network client for supervisor."""

from .client import _SupervisorComponentClient
from .models.network import (
    AccessPoint,
    AccessPointList,
    NetworkInfo,
    NetworkInterface,
    NetworkInterfaceConfig,
    VlanConfig,
)


class NetworkClient(_SupervisorComponentClient):
    """Handles network access in supervisor."""

    async def info(self) -> NetworkInfo:
        """Get network info."""
        result = await self._client.get("network/info")
        return NetworkInfo.from_dict(result.data)

    async def reload(self) -> None:
        """Reload network info caches."""
        await self._client.post("network/reload")

    async def interface_info(self, interface: str) -> NetworkInterface:
        """Get network interface info."""
        result = await self._client.get(f"network/interface/{interface}/info")
        return NetworkInterface.from_dict(result.data)

    async def update_interface(
        self, interface: str, config: NetworkInterfaceConfig
    ) -> None:
        """Update a network interface."""
        await self._client.post(
            f"network/interface/{interface}/update", json=config.to_dict()
        )

    async def access_points(self, interface: str) -> list[AccessPoint]:
        """Get access points visible to a wireless interface."""
        result = await self._client.get(f"network/interface/{interface}/accesspoints")
        return AccessPointList.from_dict(result.data).accesspoints

    async def save_vlan(
        self, interface: str, vlan: int, config: VlanConfig | None = None
    ) -> None:
        """Create or update a vlan for an ethernet interface."""
        await self._client.post(
            f"network/interface/{interface}/vlan/{vlan}",
            json=config.to_dict() if config else None,
        )
