"""Go2rtc client exceptions."""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any

from aiohttp import ClientError
from mashumaro.exceptions import (
    ExtraKeysError,
    InvalidFieldValue,
    MissingDiscriminatorError,
    MissingField,
    SuitableVariantNotFoundError,
    UnserializableDataError,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine


class Go2RtcClientError(Exception):
    """Base exception for go2rtc client."""


class Go2RtcVersionError(Exception):
    """Base exception for go2rtc client."""

    def __init__(
        self,
        server_version: str | None,
        min_version_supported: str,
        max_version_supported: str,
    ) -> None:
        """Initialize."""
        self._server_version = server_version
        self._min_version_supported = min_version_supported
        self._max_version_supported = max_version_supported

    def __str__(self) -> str:
        """Return exception message."""
        return (
            f"server version '{self._server_version}' not "
            f">= {self._min_version_supported} and < {self._max_version_supported}"
        )


def handle_error[**_P, _R](
    func: Callable[_P, Coroutine[Any, Any, _R]],
) -> Callable[_P, Coroutine[Any, Any, _R]]:
    """Wrap aiohttp and mashumaro errors."""

    @wraps(func)
    async def _func(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await func(*args, **kwargs)
        except (
            ClientError,
            ExtraKeysError,
            InvalidFieldValue,
            MissingDiscriminatorError,
            MissingField,
            SuitableVariantNotFoundError,
            UnserializableDataError,
        ) as exc:
            raise Go2RtcClientError from exc

    return _func
