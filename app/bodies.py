"""Constantes des corps calculés et des ayanamsas supportés."""

import swisseph as swe

CALC_BODIES: dict[str, int] = {
    "sun": swe.SUN,
    "moon": swe.MOON,
    "mercury": swe.MERCURY,
    "venus": swe.VENUS,
    "mars": swe.MARS,
    "jupiter": swe.JUPITER,
    "saturn": swe.SATURN,
    "uranus": swe.URANUS,
    "neptune": swe.NEPTUNE,
    "pluto": swe.PLUTO,
    "rahu": swe.MEAN_NODE,
}
"""Corps calculés directement via pyswisseph. Ketu (= rahu + 180°) n'y figure
pas : il est dérivé, jamais appelé séparément."""

ALL_BODY_IDS: tuple[str, ...] = (*CALC_BODIES.keys(), "ketu")
"""Les 12 corps du contrat d'API, dans l'ordre attendu en sortie."""

AYANAMSA_IDS: dict[str, int] = {
    "fagan_bradley": swe.SIDM_FAGAN_BRADLEY,
    "lahiri": swe.SIDM_LAHIRI,
    "raman": swe.SIDM_RAMAN,
    "krishnamurti": swe.SIDM_KRISHNAMURTI,
    "true_citra": swe.SIDM_TRUE_CITRA,
}
