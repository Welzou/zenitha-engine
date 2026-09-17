"""Positions sidérales et équatoriales des 12 corps à un instant donné."""

import threading
from dataclasses import dataclass

import swisseph as swe

from app import bodies, schemas

_ECLIPTIC_FLAGS = swe.FLG_MOSEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
_EQUATORIAL_FLAGS = swe.FLG_MOSEPH | swe.FLG_SPEED | swe.FLG_EQUATORIAL

# Le mode sidéral est en stockage thread-local dans la wheel utilisée en dev
# (vérifié : un thread qui n'arme rien lit le défaut, pas le mode du voisin),
# donc ce verrou n'y protège rien. Il couvre le VPS, où pyswisseph est compilé
# depuis les sources et où ce détail de compilation n'est pas garanti : sans
# TLS, deux requêtes d'ayanamsas différents échangeraient leur zodiaque en
# silence. Coût : 0,4 ms sérialisés par appel.
_sid_mode_lock = threading.Lock()


@dataclass(frozen=True)
class ChartPositions:
    """Sortie de calcul : les 12 positions, l'ayanamsa retenu et le GST.

    `gst_deg` ne fait pas partie du contrat d'API ; il n'existe que pour
    alimenter le calcul des lignes.
    """

    positions: list[schemas.PositionOut]
    ayanamsa: schemas.AyanamsaOut
    gst_deg: float


def _position(
    body: schemas.BodyId,
    ecliptic: tuple[float, ...],
    equatorial: tuple[float, ...],
) -> schemas.PositionOut:
    lon = ecliptic[0] % 360
    return schemas.PositionOut(
        body=body,
        lon_sidereal=lon,
        sign=bodies.SIGN_IDS[int(lon // 30)],
        deg_in_sign=lon % 30,
        ra=equatorial[0] % 360,
        dec=equatorial[1],
        retrograde=ecliptic[3] < 0,
    )


def _ketu(rahu: schemas.PositionOut) -> schemas.PositionOut:
    lon = (rahu.lon_sidereal + 180) % 360
    return schemas.PositionOut(
        body="ketu",
        lon_sidereal=lon,
        sign=bodies.SIGN_IDS[int(lon // 30)],
        deg_in_sign=lon % 30,
        ra=(rahu.ra + 180) % 360,
        dec=-rahu.dec,
        retrograde=rahu.retrograde,
    )


def compute_positions(
    jd_ut: float,
    ayanamsa: schemas.AyanamsaId = "fagan_bradley",
) -> ChartPositions:
    """Calcule les 12 positions du thème pour un instant et un ayanamsa donnés.

    La longitude est sidérale, ra/dec restent tropicales : l'ayanamsa déplace
    le tableau des positions, jamais les lignes sur la carte.
    """
    with _sid_mode_lock:
        swe.set_sid_mode(bodies.AYANAMSA_IDS[ayanamsa])
        raw = {
            body: (
                swe.calc_ut(jd_ut, code, _ECLIPTIC_FLAGS)[0],
                swe.calc_ut(jd_ut, code, _EQUATORIAL_FLAGS)[0],
            )
            for body, code in bodies.CALC_BODIES.items()
        }
        ayanamsa_deg = swe.get_ayanamsa_ut(jd_ut)

    computed = {body: _position(body, *values) for body, values in raw.items()}

    return ChartPositions(
        positions=[*computed.values(), _ketu(computed["rahu"])],
        ayanamsa=schemas.AyanamsaOut(id=ayanamsa, value_deg=ayanamsa_deg),
        gst_deg=swe.sidtime(jd_ut) * 15,
    )
