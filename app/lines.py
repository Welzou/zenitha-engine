"""Lignes d'astrocartographie : méridiens MC/IC et courbes de lever/coucher."""

import math
from typing import NamedTuple

from app import schemas

LINE_MIN_LAT = -89.0
LINE_MAX_LAT = 89.0
_ANTIMERIDIAN_JUMP_DEG = 180.0

Point = tuple[float, float]


def norm180(deg: float) -> float:
    """Ramène un angle dans ]-180, 180], borne haute incluse."""
    # `((deg + 180) % 360) - 180` rendrait -180 sur l'antiméridien, que la
    # convention du projet place à +180.
    return 180 - ((180 - deg) % 360)


class Meridians(NamedTuple):
    mc: schemas.LineGeometry
    ic: schemas.LineGeometry


class AcDc(NamedTuple):
    ac: schemas.LineGeometry
    dc: schemas.LineGeometry


def _meridian(lon: float) -> schemas.LineGeometry:
    # Deux points suffisent : à longitude constante, le segment est exact aussi
    # bien en Mercator (droite verticale) qu'en projection globe (grand cercle).
    return schemas.LineGeometry(
        type="MultiLineString",
        coordinates=[[(lon, LINE_MIN_LAT), (lon, LINE_MAX_LAT)]],
    )


def mc_ic_lines(ra: float, gst: float) -> Meridians:
    """Méridiens supérieur et inférieur d'un corps d'ascension droite `ra`."""
    mc_lon = norm180(ra - gst)
    return Meridians(mc=_meridian(mc_lon), ic=_meridian(norm180(mc_lon + 180)))


def _latitudes(step: float) -> list[float]:
    count = round((LINE_MAX_LAT - LINE_MIN_LAT) / step)
    # Recalculé depuis l'origine à chaque pas : une accumulation dériverait.
    return [LINE_MIN_LAT + index * step for index in range(count + 1)]


def _horizon_longitudes(
    ra: float,
    dec: float,
    gst: float,
    lat: float,
) -> tuple[float, float] | None:
    """Longitudes de lever et de coucher à une latitude, `None` si circumpolaire."""
    ratio = math.tan(math.radians(lat)) * math.tan(math.radians(dec))
    if abs(ratio) > 1:
        return None

    hour_angle = math.degrees(math.acos(-ratio))
    return norm180(ra - hour_angle - gst), norm180(ra + hour_angle - gst)


def _multiline(points: list[Point | None]) -> schemas.LineGeometry:
    segments: list[list[Point]] = []
    current: list[Point] = []

    for point in points:
        if point is None:
            segments.append(current)
            current = []
            continue
        if current and abs(point[0] - current[-1][0]) > _ANTIMERIDIAN_JUMP_DEG:
            segments.append(current)
            current = []
        current.append(point)
    segments.append(current)

    # Un segment d'un seul point n'est pas un LineString valide. Il apparaît
    # quand la courbe franchit l'antiméridien juste avant de s'interrompre.
    return schemas.LineGeometry(
        type="MultiLineString",
        coordinates=[segment for segment in segments if len(segment) >= 2],
    )


def ac_dc_lines(ra: float, dec: float, gst: float, step: float) -> AcDc:
    """Courbes de lever et de coucher d'un corps, échantillonnées en latitude."""
    rising: list[Point | None] = []
    setting: list[Point | None] = []

    for lat in _latitudes(step):
        found = _horizon_longitudes(ra, dec, gst, lat)
        rising.append(None if found is None else (found[0], lat))
        setting.append(None if found is None else (found[1], lat))

    return AcDc(ac=_multiline(rising), dc=_multiline(setting))
