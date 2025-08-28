"""Constants for aiohasupervisor."""

from enum import StrEnum

from aiohttp import ClientTimeout

DEFAULT_TIMEOUT = ClientTimeout(total=10)
TIMEOUT_60_SECONDS = ClientTimeout(total=60)


class ResponseType(StrEnum):
    """Expected response type."""

    NONE = "none"
    JSON = "json"
    STREAM = "stream"
    TEXT = "text"
