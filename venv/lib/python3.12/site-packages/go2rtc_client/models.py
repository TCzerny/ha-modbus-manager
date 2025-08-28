"""Go2rtc Python models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from awesomeversion import AwesomeVersion
from mashumaro import field_options
from mashumaro.mixins.orjson import DataClassORJSONMixin
from mashumaro.types import SerializationStrategy


class _AwesomeVersionSerializer(SerializationStrategy):
    def serialize(self, value: AwesomeVersion) -> str:
        return str(value)

    def deserialize(self, value: str) -> AwesomeVersion:
        return AwesomeVersion(value)


@dataclass
class ApplicationInfo(DataClassORJSONMixin):
    """Application info model.

    Currently only the server version is exposed.
    """

    version: AwesomeVersion = field(
        metadata=field_options(serialization_strategy=_AwesomeVersionSerializer())
    )


@dataclass
class Streams(DataClassORJSONMixin):
    """Streams model."""

    streams: dict[str, Stream]


@dataclass
class Stream:
    """Stream model."""

    producers: list[Producer]

    @classmethod
    def __pre_deserialize__(cls, d: dict[Any, Any]) -> dict[Any, Any]:
        """Pre deserialize."""
        # Ensure producers is always a list
        if "producers" in d and d["producers"] is None:
            d["producers"] = []

        return d


@dataclass
class Producer:
    """Producer model."""

    url: str


@dataclass
class WebRTCSdp(DataClassORJSONMixin):
    """WebRTC SDP model."""

    type: Literal["offer", "answer"]
    sdp: str


@dataclass
class WebRTCSdpOffer(WebRTCSdp):
    """WebRTC SDP offer model."""

    type: Literal["offer"] = field(default="offer", init=False)


@dataclass
class WebRTCSdpAnswer(WebRTCSdp):
    """WebRTC SDP answer model."""

    type: Literal["answer"] = field(default="answer", init=False)
