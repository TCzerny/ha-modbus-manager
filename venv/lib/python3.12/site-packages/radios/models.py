"""Models for the Radio Browser API."""

# pylint: disable=too-few-public-methods
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import cast

import pycountry
from awesomeversion import AwesomeVersion
from mashumaro import field_options
from mashumaro.mixins.orjson import DataClassORJSONMixin
from mashumaro.types import SerializationStrategy


class CommaSeparatedString(SerializationStrategy):
    """String serialization strategy to handle comma separated strings."""

    def serialize(self, value: list[str]) -> str:
        """Serialize a list of strings to a comma separated value."""
        return ",".join(value)

    def deserialize(self, value: str) -> list[str]:
        """Deserialize a comma separated value to a list of strings."""
        return [item.strip() for item in value.split(",")]


@dataclass
# pylint: disable=too-many-instance-attributes
class Stats(DataClassORJSONMixin):
    """Object holding the Radio Browser stats."""

    supported_version: int
    software_version: AwesomeVersion
    status: str
    stations: int
    stations_broken: int
    tags: int
    clicks_last_hour: int
    clicks_last_day: int
    languages: int
    countries: int


@dataclass
# pylint: disable=too-many-instance-attributes
class Station(DataClassORJSONMixin):
    """Object information for a station from the Radio Browser."""

    bitrate: int
    change_uuid: str = field(metadata=field_options(alias="changeuuid"))
    click_count: int = field(metadata=field_options(alias="clickcount"))
    click_timestamp: datetime | None = field(
        metadata=field_options(alias="clicktimestamp_iso8601")
    )
    click_trend: int = field(metadata=field_options(alias="clicktrend"))
    codec: str
    country_code: str = field(metadata=field_options(alias="countrycode"))
    favicon: str
    latitude: float | None = field(metadata=field_options(alias="geo_lat"))
    longitude: float | None = field(metadata=field_options(alias="geo_long"))
    has_extended_info: bool
    hls: bool
    homepage: str
    iso_3166_2: str | None
    language: list[str] = field(
        metadata=field_options(serialization_strategy=CommaSeparatedString())
    )
    language_codes: list[str] = field(
        metadata=field_options(
            alias="languagecodes", serialization_strategy=CommaSeparatedString()
        )
    )
    lastchange_time: datetime | None = field(
        metadata=field_options(alias="lastchangetime_iso8601")
    )
    lastcheckok: bool
    last_check_ok_time: datetime | None = field(
        metadata=field_options(alias="lastcheckoktime_iso8601")
    )
    last_check_time: datetime | None = field(
        metadata=field_options(alias="lastchecktime_iso8601")
    )
    last_local_check_time: datetime | None = field(
        metadata=field_options(alias="lastlocalchecktime_iso8601")
    )
    name: str
    ssl_error: int
    state: str
    uuid: str = field(metadata=field_options(alias="stationuuid"))
    tags: list[str] = field(
        metadata=field_options(serialization_strategy=CommaSeparatedString())
    )
    url_resolved: str
    url: str
    votes: int

    @property
    def country(self) -> str | None:
        """Return country name of this station.

        Returns
        -------
            Country name or None if no country code is set.

        """
        if resolved_country := pycountry.countries.get(alpha_2=self.country_code):
            return cast(str, resolved_country.name)
        return None


@dataclass
class Country(DataClassORJSONMixin):
    """Object information for a Counbtry from the Radio Browser."""

    code: str
    name: str
    station_count: str = field(metadata=field_options(alias="stationcount"))

    @property
    def favicon(self) -> str:
        """Return the favicon URL for the country.

        Returns
        -------
            URL to the favicon.

        """
        return f"https://flagcdn.com/256x192/{self.code.lower()}.png"


@dataclass
class Language(DataClassORJSONMixin):
    """Object information for a Language from the Radio Browser."""

    code: str | None = field(metadata=field_options(alias="iso_639"))
    name: str
    station_count: str = field(metadata=field_options(alias="stationcount"))

    @property
    def favicon(self) -> str | None:
        """Return the favicon URL for the language.

        Returns
        -------
            URL to the favicon.

        """
        if self.code:
            return f"https://flagcdn.com/256x192/{self.code.lower()}.png"
        return None


@dataclass
class Tag(DataClassORJSONMixin):
    """Object information for a Tag from the Radio Browser."""

    name: str
    station_count: str = field(metadata=field_options(alias="stationcount"))
