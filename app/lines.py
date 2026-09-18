"""Lignes d'astrocartographie : méridiens MC/IC et courbes de lever/coucher."""

import math
from collections.abc import Sequence
from typing import NamedTuple

from app import schemas

LINE_MIN_LAT = -89.0
LINE_MAX_LAT = 89.0
_ANTIMERIDIAN_JUMP_DEG = 180.0
_MAX_LONGITUDE_GAP_DEG = 2.0
# Garde-fou seulement : à pas 0,5° la bisection s'arrête d'elle-même autour de
# la profondeur 12, et pousser le plafond plus loin n'ajoute aucun point.
_MAX_REFINEMENT_DEPTH = 16

Point = tuple[float, float]
Sample = tuple[float, float]  # (latitude, angle horaire)


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


def _hour_angle(dec: float, lat: float) -> float | None:
    """Angle horaire du lever, `None` si le corps est circumpolaire à cette latitude."""
    ratio = math.tan(math.radians(lat)) * math.tan(math.radians(dec))
    if abs(ratio) > 1:
        return None

    return math.degrees(math.acos(-ratio))


def _apex_hour_angle(dec: float, lat: float) -> float:
    # À la latitude limite le corps rase l'horizon sans le franchir : au méridien
    # inférieur quand latitude et déclinaison sont de même signe, au supérieur
    # sinon. Déduit du signe et non de `acos`, dont le ratio déborde de 1 au
    # dernier bit précisément là où l'on veut poser ce point.
    return 180.0 if (lat > 0) == (dec > 0) else 0.0


def _longitudes(ra: float, gst: float, hour_angle: float) -> tuple[float, float]:
    if hour_angle == 180.0:
        # Apex : les deux courbes s'y rejoignent. `ra - 180` et `ra + 180` sont
        # égaux modulo 360 sans l'être au bit près, donc on n'en calcule qu'un
        # pour que la jonction soit exacte et pas approchée.
        apex = norm180(ra + 180 - gst)
        return apex, apex

    return norm180(ra - hour_angle - gst), norm180(ra + hour_angle - gst)


def _horizon_longitudes(
    ra: float,
    dec: float,
    gst: float,
    lat: float,
) -> tuple[float, float] | None:
    """Longitudes de lever et de coucher à une latitude, `None` si circumpolaire."""
    hour_angle = _hour_angle(dec, lat)
    if hour_angle is None:
        return None

    return _longitudes(ra, gst, hour_angle)


def _subdivide(dec: float, left: Sample, right: Sample, depth: int) -> list[Sample]:
    if depth > _MAX_REFINEMENT_DEPTH:
        return []
    if abs(right[1] - left[1]) <= _MAX_LONGITUDE_GAP_DEG:
        return []

    mid_lat = (left[0] + right[0]) / 2
    mid_hour_angle = _hour_angle(dec, mid_lat)
    if mid_hour_angle is None:
        return []

    middle = (mid_lat, mid_hour_angle)
    return [
        *_subdivide(dec, left, middle, depth + 1),
        middle,
        *_subdivide(dec, middle, right, depth + 1),
    ]


def _horizon_samples(dec: float, step: float) -> list[Sample]:
    """Latitudes de lever, apex compris, resserrées là où la courbe tourne vite."""
    samples = [
        (lat, hour_angle)
        for lat in _latitudes(step)
        if (hour_angle := _hour_angle(dec, lat)) is not None
    ]

    limit = 90 - abs(dec)
    if limit <= LINE_MAX_LAT:
        samples += [
            (limit, _apex_hour_angle(dec, limit)),
            (-limit, _apex_hour_angle(dec, -limit)),
        ]
    samples.sort()

    densified: list[Sample] = []
    for left, right in zip(samples, samples[1:]):
        densified.append(left)
        densified.extend(_subdivide(dec, left, right, 1))
    densified.append(samples[-1])

    return densified


def _antimeridian_crossing(left: Point, right: Point) -> tuple[Point, Point]:
    """Points de sortie et d'entrée de carte, à la latitude de la traversée."""
    exit_lon = 180.0 if left[0] > 0 else -180.0
    entry_lon = -exit_lon

    to_edge = abs(exit_lon - left[0])
    from_edge = abs(right[0] - entry_lon)
    ratio = to_edge / (to_edge + from_edge)
    lat = left[1] + ratio * (right[1] - left[1])

    return (exit_lon, lat), (entry_lon, lat)


def _split_segments(points: Sequence[Point | None]) -> list[list[Point]]:
    segments: list[list[Point]] = []
    current: list[Point] = []

    for point in points:
        if point is None:
            segments.append(current)
            current = []
            continue
        if current and abs(point[0] - current[-1][0]) > _ANTIMERIDIAN_JUMP_DEG:
            # La courbe sort d'un bord de carte et rentre par l'autre. Sans ces
            # deux points elle s'arrête avant le bord, et un apex posé sur
            # l'antiméridien se retrouve seul dans son segment.
            leaving, entering = _antimeridian_crossing(current[-1], point)
            current.append(leaving)
            segments.append(current)
            current = [entering]
        current.append(point)
    segments.append(current)

    return segments


def _multiline(points: Sequence[Point | None]) -> schemas.LineGeometry:
    # Filet de sécurité : un segment d'un seul point n'est pas un LineString
    # valide. Depuis l'interpolation ci-dessus, aucune courbe n'en produit.
    return schemas.LineGeometry(
        type="MultiLineString",
        coordinates=[
            segment for segment in _split_segments(points) if len(segment) >= 2
        ],
    )


def ac_dc_lines(ra: float, dec: float, gst: float, step: float) -> AcDc:
    """Courbes de lever et de coucher d'un corps, échantillonnées en latitude."""
    rising: list[Point] = []
    setting: list[Point] = []

    for lat, hour_angle in _horizon_samples(dec, step):
        ac_lon, dc_lon = _longitudes(ra, gst, hour_angle)
        rising.append((ac_lon, lat))
        setting.append((dc_lon, lat))

    return AcDc(ac=_multiline(rising), dc=_multiline(setting))
