"""Go2rtc websocket messages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Any, ClassVar

from mashumaro import field_options
from mashumaro.config import BaseConfig
from mashumaro.mixins.orjson import DataClassORJSONMixin
from mashumaro.types import Discriminator
from webrtc_models import (
    RTCIceServer,  # noqa: TCH002 # Mashumaro needs the import to generate the correct code
)


@dataclass(frozen=True)
class WsMessage:
    """Websocket message."""

    TYPE: ClassVar[str]

    def __post_serialize__(self, d: dict[Any, Any]) -> dict[Any, Any]:
        """Add type to serialized dict."""
        # ClassVar will not serialize by default
        d["type"] = self.TYPE
        return d


@dataclass(frozen=True)
class BaseMessage(WsMessage, DataClassORJSONMixin):
    """Base message class."""

    class Config(BaseConfig):
        """Config for BaseMessage."""

        serialize_by_alias = True
        discriminator = Discriminator(
            field="type",
            include_subtypes=True,
            variant_tagger_fn=lambda cls: cls.TYPE,
        )


@dataclass(frozen=True)
class WebRTCCandidate(BaseMessage):
    """WebRTC ICE candidate message."""

    TYPE = "webrtc/candidate"
    candidate: str = field(metadata=field_options(alias="value"))


@dataclass(frozen=True)
class WebRTC(BaseMessage):
    """WebRTC message."""

    TYPE = "webrtc"
    value: Annotated[
        WebRTCOffer | WebRTCValue,
        Discriminator(
            field="type",
            include_subtypes=True,
            variant_tagger_fn=lambda cls: cls.TYPE,
        ),
    ]


@dataclass(frozen=True)
class WebRTCValue(WsMessage):
    """WebRTC value for WebRTC message."""

    sdp: str


@dataclass(frozen=True)
class WebRTCOffer(WebRTCValue):
    """WebRTC offer message."""

    TYPE = "offer"
    ice_servers: list[RTCIceServer]

    def __pre_serialize__(self) -> WebRTCOffer:
        """Pre serialize.

        Go2rtc supports only ice_servers with urls as list of strings.
        """
        for server in self.ice_servers:
            if isinstance(server.urls, str):
                server.urls = [server.urls]

        return self

    def to_json(self, **kwargs: Any) -> str:
        """Convert to json."""
        return WebRTC(self).to_json(**kwargs)


@dataclass(frozen=True)
class WebRTCAnswer(WebRTCValue):
    """WebRTC answer message."""

    TYPE = "answer"


@dataclass(frozen=True)
class WsError(BaseMessage):
    """Error message."""

    TYPE = "error"
    error: str = field(metadata=field_options(alias="value"))


ReceiveMessages = WebRTCAnswer | WebRTCCandidate | WsError
SendMessages = WebRTCCandidate | WebRTCOffer
