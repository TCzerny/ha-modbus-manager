from __future__ import annotations

__version__ = "0.1.1"

import asyncio
from pathlib import Path

BLUETOOTH_DEVICE_PATH = Path("/sys/class/bluetooth")
UART_DEVICE_PATH = Path("/sys/bus/serial/devices")


class NotAUARTDeviceError(ValueError):
    """Raised when a device is not a UART device."""


__all__ = [
    "BluetoothDevice",
    "NotAUARTDeviceError",
    "UARTDevice",
]


class BluetoothDevice:
    """Bluetooth device object."""

    __slots__ = ("device_path", "hci", "path", "uart_device")

    def __init__(self, hci: int) -> None:
        """Initialize a BluetoothDevice object."""
        self.hci = hci
        self.path = BLUETOOTH_DEVICE_PATH / f"hci{self.hci}"
        self.device_path = self.path / "device"
        self.uart_device: UARTDevice | None = None

    async def async_setup(self) -> None:
        """Set up a Bluetooth device."""
        await asyncio.get_running_loop().run_in_executor(None, self.setup)

    def setup(self) -> None:
        """Create a UARTDevice object."""
        path = self.device_path.readlink()
        self.uart_device = UARTDevice(path.parts[-1])
        self.uart_device.setup()


class UARTDevice:
    """UART device object."""

    __slots__ = (
        "id_str",
        "manufacturer",
        "path",
        "product",
    )

    def __init__(self, id_str: str) -> None:
        """Initialize a UARTDevice object."""
        if "-" not in id_str:
            raise NotAUARTDeviceError(f"{id_str} is not a UART device")
        self.id_str = id_str  # serial0-0
        self.manufacturer: str | None = None
        self.product: str | None = None
        self.path = UART_DEVICE_PATH / id_str

    async def async_setup(self) -> None:
        """Set up a UART device."""
        await asyncio.get_running_loop().run_in_executor(None, self.setup)

    def setup(self) -> None:
        """Read the UART device."""
        data: dict[str, str] = {
            parts[0]: parts[2]
            for line in self.path.joinpath("uevent").read_text().strip().splitlines()
            if (parts := line.partition("="))
        }
        if of_compatible_0 := data.get("OF_COMPATIBLE_0"):
            self.manufacturer = of_compatible_0.partition(",")[0]
        if (mod_alias := data.get("MODALIAS")) and "," in mod_alias:
            self.product = mod_alias.split(",")[-1]
