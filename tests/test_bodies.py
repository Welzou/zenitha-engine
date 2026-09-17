import json
from pathlib import Path

import swisseph as swe

from app import bodies

FIXTURES = Path(__file__).parent / "fixtures" / "reference_charts.json"

CALC_BODY_CONSTANT_NAMES = {
    "sun": "SUN",
    "moon": "MOON",
    "mercury": "MERCURY",
    "venus": "VENUS",
    "mars": "MARS",
    "jupiter": "JUPITER",
    "saturn": "SATURN",
    "uranus": "URANUS",
    "neptune": "NEPTUNE",
    "pluto": "PLUTO",
    "rahu": "MEAN_NODE",
}

AYANAMSA_CONSTANT_NAMES = {
    "fagan_bradley": "SIDM_FAGAN_BRADLEY",
    "lahiri": "SIDM_LAHIRI",
    "raman": "SIDM_RAMAN",
    "krishnamurti": "SIDM_KRISHNAMURTI",
    "true_citra": "SIDM_TRUE_CITRA",
}


class TestCalcBodies:
    def test_resolves_to_named_swisseph_constant(self):
        assert set(bodies.CALC_BODIES) == set(CALC_BODY_CONSTANT_NAMES)
        for body_id, constant_name in CALC_BODY_CONSTANT_NAMES.items():
            assert bodies.CALC_BODIES[body_id] == getattr(swe, constant_name)

    def test_ketu_is_not_a_calculated_body(self):
        assert "ketu" not in bodies.CALC_BODIES


class TestAllBodyIds:
    def test_matches_reference_fixture_order_and_names(self):
        data = json.loads(FIXTURES.read_text(encoding="utf-8"))
        fixture_bodies = [p["body"] for p in data["charts"][0]["positions"]]

        assert fixture_bodies == list(bodies.ALL_BODY_IDS)


class TestAyanamsaIds:
    def test_resolves_to_named_swisseph_constant(self):
        assert set(bodies.AYANAMSA_IDS) == set(AYANAMSA_CONSTANT_NAMES)
        for ayanamsa_id, constant_name in AYANAMSA_CONSTANT_NAMES.items():
            assert bodies.AYANAMSA_IDS[ayanamsa_id] == getattr(swe, constant_name)
