"""Websocket client for go2rtc server."""

import asyncio
from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType

from go2rtc_client.exceptions import handle_error

from .messages import BaseMessage, ReceiveMessages, SendMessages, WebRTC, WsMessage

_LOGGER = logging.getLogger(__name__)


class Go2RtcWsClient:
    """Websocket client for go2rtc server."""

    def __init__(
        self,
        session: ClientSession,
        server_url: str,
        *,
        source: str | None = None,
        destination: str | None = None,
    ) -> None:
        """Initialize Client."""
        if source:
            if destination:
                msg = "Source and destination cannot be set at the same time"
                raise ValueError(msg)
            params = {"src": source}
        elif destination:
            params = {"dst": destination}
        else:
            msg = "Source or destination must be set"
            raise ValueError(msg)

        self._server_url = server_url
        self._session = session
        self._params = params
        self._client: ClientWebSocketResponse | None = None
        self._rx_task: asyncio.Task[None] | None = None
        self._subscribers: list[Callable[[ReceiveMessages], None]] = []
        self._connect_lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        """Return if we're currently connected."""
        return self._client is not None and not self._client.closed

    @handle_error
    async def connect(self) -> None:
        """Connect to device."""
        async with self._connect_lock:
            if self.connected:
                return

            _LOGGER.debug("Trying to connect to %s", self._server_url)
            self._client = await self._session.ws_connect(
                urljoin(self._server_url, "/api/ws"), params=self._params
            )

            self._rx_task = asyncio.create_task(self._receive_messages())
            _LOGGER.info("Connected to %s", self._server_url)

    @handle_error
    async def close(self) -> None:
        """Close connection."""
        if self.connected:
            if TYPE_CHECKING:
                assert self._client is not None
            client = self._client
            self._client = None
            await client.close()

        if self._rx_task:
            task = self._rx_task
            self._rx_task = None
            task.cancel()
            await task

    @handle_error
    async def send(self, message: SendMessages) -> None:
        """Send a message."""
        if not self.connected:
            await self.connect()

        if TYPE_CHECKING:
            assert self._client is not None

        await self._client.send_str(message.to_json())

    def _process_text_message(self, data: Any) -> None:
        """Process text message."""
        try:
            message: WsMessage = BaseMessage.from_json(data)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Invalid message received: %s", data)
        else:
            if isinstance(message, WebRTC):
                message = message.value
            if not isinstance(message, ReceiveMessages):
                _LOGGER.error("Received unexpected message: %s", message)
                return
            for subscriber in self._subscribers:
                try:
                    subscriber(message)
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Error on subscriber callback")

    async def _receive_messages(self) -> None:
        """Receive messages."""
        if TYPE_CHECKING:
            assert self._client

        while self.connected:
            msg = await self._client.receive()
            match msg.type:
                case (
                    WSMsgType.CLOSE
                    | WSMsgType.CLOSED
                    | WSMsgType.CLOSING
                    | WSMsgType.PING
                    | WSMsgType.PONG
                ):
                    break
                case WSMsgType.ERROR:
                    _LOGGER.error("Error received: %s", msg.data)
                case WSMsgType.TEXT:
                    self._process_text_message(msg.data)
                case _:
                    _LOGGER.warning("Received unknown message: %s", msg)

    def subscribe(
        self, callback: Callable[[ReceiveMessages], None]
    ) -> Callable[[], None]:
        """Subscribe to messages."""

        def _unsubscribe() -> None:
            self._subscribers.remove(callback)

        self._subscribers.append(callback)
        return _unsubscribe
