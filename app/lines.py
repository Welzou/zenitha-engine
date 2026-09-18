"""Lignes d'astrocartographie : méridiens MC/IC."""

from typing import NamedTuple

from app import schemas

MERIDIAN_MIN_LAT = -89.0
MERIDIAN_MAX_LAT = 89.0


def norm180(deg: float) -> float:
    """Ramène un angle dans ]-180, 180], borne haute incluse."""
    # `((deg + 180) % 360) - 180` rendrait -180 sur l'antiméridien, que la
    # convention du projet place à +180.
    return 180 - ((180 - deg) % 360)


class Meridians(NamedTuple):
    mc: schemas.LineGeometry
    ic: schemas.LineGeometry


def _meridian(lon: float) -> schemas.LineGeometry:
    # Deux points suffisent : à longitude constante, le segment est exact aussi
    # bien en Mercator (droite verticale) qu'en projection globe (grand cercle).
    return schemas.LineGeometry(
        type="MultiLineString",
        coordinates=[[(lon, MERIDIAN_MIN_LAT), (lon, MERIDIAN_MAX_LAT)]],
    )


def mc_ic_lines(ra: float, gst: float) -> Meridians:
    """Méridiens supérieur et inférieur d'un corps d'ascension droite `ra`."""
    mc_lon = norm180(ra - gst)
    return Meridians(mc=_meridian(mc_lon), ic=_meridian(norm180(mc_lon + 180)))
