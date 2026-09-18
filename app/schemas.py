"""Schémas pydantic v2 du contrat d'API (entrée/sortie de `POST /v1/chart`)."""

from datetime import date, datetime, time, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

AyanamsaId = Literal[
    "fagan_bradley",
    "lahiri",
    "raman",
    "krishnamurti",
    "true_citra",
]

BodyId = Literal[
    "sun",
    "moon",
    "mercury",
    "venus",
    "mars",
    "jupiter",
    "saturn",
    "uranus",
    "neptune",
    "pluto",
    "rahu",
    "ketu",
]

Sign = Literal[
    "aries",
    "taurus",
    "gemini",
    "cancer",
    "leo",
    "virgo",
    "libra",
    "scorpio",
    "sagittarius",
    "capricorn",
    "aquarius",
    "pisces",
]

Angle = Literal["mc", "ic", "ac", "dc"]

ErrorCode = Literal[
    "TZ_NOT_FOUND",
    "TIME_AMBIGUOUS",
    "TIME_NONEXISTENT",
    "DATE_OUT_OF_RANGE",
]


class ChartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    time: time
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    ayanamsa: AyanamsaId = "fagan_bradley"
    fold: Literal[0, 1] | None = None
    lat_step_deg: float = Field(default=0.5, ge=0.1, le=2)


class InstantOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tz: str
    utc_offset_minutes: int
    utc: datetime
    jd_ut: float

    @field_serializer("utc")
    def _serialize_utc(self, value: datetime) -> str:
        # pydantic v2 rend "+00:00" pour un datetime aware ; le contrat d'API
        # promet un "Z" (cf. exemple de la spec technique).
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class AyanamsaOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: AyanamsaId
    value_deg: float


class PositionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: BodyId
    lon_sidereal: float
    sign: Sign
    deg_in_sign: float
    ra: float
    dec: float
    retrograde: bool


class LineGeometry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["MultiLineString"]
    coordinates: list[list[tuple[float, float]]]


class LineOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    body: BodyId
    angle: Angle
    geometry: LineGeometry


class ChartResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instant: InstantOut
    ayanamsa: AyanamsaOut
    positions: list[PositionOut]
    lines: list[LineOut]


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorCode
    detail: str | dict[str, object]
