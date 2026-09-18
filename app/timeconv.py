"""Conversion date/heure civile locale → temps universel, fuseau historique."""

import datetime as dt
from typing import ClassVar
from zoneinfo import ZoneInfo

import swisseph as swe
import timezonefinder

from app import schemas

MIN_DATE = dt.date(1800, 1, 1)
MAX_DATE = dt.date(2199, 12, 31)


class EngineError(Exception):
    """Erreur métier : se traduit en 400 `{"error": code, "detail": detail}`."""

    code: ClassVar[schemas.ErrorCode]

    def __init__(self, detail: str | dict[str, object]) -> None:
        super().__init__(detail)
        self.detail = detail


class DateOutOfRange(EngineError):
    code = "DATE_OUT_OF_RANGE"


class TzNotFound(EngineError):
    code = "TZ_NOT_FOUND"


class TimeAmbiguous(EngineError):
    code = "TIME_AMBIGUOUS"


class TimeNonexistent(EngineError):
    code = "TIME_NONEXISTENT"


def _offset_minutes(moment: dt.datetime) -> int:
    return round(moment.utcoffset().total_seconds() / 60)


def resolve_instant(
    date: dt.date,
    time: dt.time,
    lat: float,
    lng: float,
    fold: int | None = None,
) -> schemas.InstantOut:
    """Résout un instant de naissance civil local en instant universel."""
    if not MIN_DATE <= date <= MAX_DATE:
        raise DateOutOfRange({"min": MIN_DATE.isoformat(), "max": MAX_DATE.isoformat()})

    # Fonction de module et non une instance à nous : `TimezoneFinder` est
    # documenté « une instance par thread », or cette route est synchrone et
    # tourne donc sur le threadpool de Starlette. Un fuseau faux ne se voit pas
    # sur la carte, il la décale d'une heure entière.
    tz = timezonefinder.timezone_at_land(lat=lat, lng=lng)
    if tz is None:
        raise TzNotFound("no timezone at these coordinates")

    zone = ZoneInfo(tz)
    naive = dt.datetime.combine(date, time)
    first = naive.replace(tzinfo=zone, fold=0)
    second = naive.replace(tzinfo=zone, fold=1)

    local = first
    if first.utcoffset() != second.utcoffset():
        # PEP 495 : l'offset varie avec fold aussi bien pour une heure sautée
        # que pour une heure vécue deux fois. Seul l'aller-retour les sépare —
        # il rend son heure murale à la seconde, pas à la première.
        roundtrip = first.astimezone(dt.timezone.utc).astimezone(zone)
        if roundtrip.replace(tzinfo=None) != naive:
            raise TimeNonexistent(f"local time skipped by a DST transition in {tz}")
        if fold is None:
            raise TimeAmbiguous(
                {"offsets": [_offset_minutes(first), _offset_minutes(second)]}
            )
        local = second if fold == 1 else first

    utc = local.astimezone(dt.timezone.utc)
    hours = utc.hour + utc.minute / 60 + utc.second / 3600

    return schemas.InstantOut(
        tz=tz,
        utc_offset_minutes=_offset_minutes(local),
        utc=utc,
        jd_ut=swe.julday(utc.year, utc.month, utc.day, hours, swe.GREG_CAL),
    )
