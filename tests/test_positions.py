import json
from pathlib import Path

import pytest
import swisseph as swe

from app import bodies, positions

FIXTURES = Path(__file__).parent / "fixtures" / "reference_charts.json"
_DATA = json.loads(FIXTURES.read_text(encoding="utf-8"))
CHARTS = _DATA["charts"]
TOL = _DATA["_meta"]["tolerances"]


@pytest.fixture(params=CHARTS, ids=[chart["id"] for chart in CHARTS])
def chart(request):
    return request.param


@pytest.fixture
def computed(chart):
    return positions.compute_positions(chart["jd_ut"], chart["ayanamsa"]["id"])


def expected_by_body(chart: dict) -> dict:
    return {position["body"]: position for position in chart["positions"]}


class TestReferenceCharts:
    def test_longitudes_ra_and_dec(self, chart, computed):
        expected = expected_by_body(chart)

        for position in computed.positions:
            want = expected[position.body]
            assert position.lon_sidereal == pytest.approx(
                want["lon_sidereal"], abs=TOL["lon_sidereal_deg"]
            )
            assert position.ra == pytest.approx(want["ra"], abs=TOL["ra_dec_deg"])
            assert position.dec == pytest.approx(want["dec"], abs=TOL["ra_dec_deg"])

    def test_sign_degree_and_retrograde(self, chart, computed):
        expected = expected_by_body(chart)

        for position in computed.positions:
            want = expected[position.body]
            assert position.sign == want["sign"]
            assert position.retrograde == want["retrograde"]
            assert position.deg_in_sign == pytest.approx(
                want["deg_in_sign"], abs=TOL["lon_sidereal_deg"]
            )

    def test_body_order_matches_the_contract(self, computed):
        assert [position.body for position in computed.positions] == list(
            bodies.ALL_BODY_IDS
        )

    def test_ayanamsa_value(self, chart, computed):
        assert computed.ayanamsa.id == chart["ayanamsa"]["id"]
        assert computed.ayanamsa.value_deg == pytest.approx(
            chart["ayanamsa"]["value_deg"], abs=TOL["ayanamsa_deg"]
        )

    def test_gst(self, chart, computed):
        assert computed.gst_deg == pytest.approx(chart["gst_deg"], abs=TOL["gst_deg"])


class TestKetuDerivation:
    def test_ketu_is_exactly_opposite_rahu(self, computed):
        by_body = {position.body: position for position in computed.positions}
        rahu, ketu = by_body["rahu"], by_body["ketu"]

        assert ketu.lon_sidereal == (rahu.lon_sidereal + 180) % 360
        assert ketu.ra == (rahu.ra + 180) % 360
        assert ketu.dec == -rahu.dec
        assert ketu.retrograde == rahu.retrograde


class TestEquatorialFrame:
    def test_equatorial_call_is_not_sidereal(self):
        # Verrouillé sur le flag et pas sur une valeur : un FLG_SIDEREAL ici ne
        # décale ra/dec que de 0,0007°, invisible sous la tolérance de 0,02° des
        # fixtures, et invisible aussi au test d'invariance ci-dessous puisque ce
        # décalage ne dépend pas de l'ayanamsa.
        assert not positions._EQUATORIAL_FLAGS & swe.FLG_SIDEREAL
        assert positions._ECLIPTIC_FLAGS & swe.FLG_SIDEREAL


class TestAyanamsaScope:
    # Règle métier : changer l'ayanamsa change le tableau, pas la carte. Ce test
    # attrape une ra/dec dérivée de la longitude sidérale, qui décalerait les 48
    # lignes d'environ 1° d'un ayanamsa à l'autre.
    def test_ayanamsa_does_not_move_the_equatorial_frame(self, chart):
        fagan = positions.compute_positions(chart["jd_ut"], "fagan_bradley")
        lahiri = positions.compute_positions(chart["jd_ut"], "lahiri")

        assert fagan.gst_deg == lahiri.gst_deg
        for left, right in zip(fagan.positions, lahiri.positions, strict=True):
            assert left.body == right.body
            assert left.ra == right.ra
            assert left.dec == right.dec

    def test_ayanamsa_does_move_the_sidereal_longitudes(self, chart):
        fagan = positions.compute_positions(chart["jd_ut"], "fagan_bradley")
        lahiri = positions.compute_positions(chart["jd_ut"], "lahiri")

        assert fagan.ayanamsa.value_deg != lahiri.ayanamsa.value_deg
        for left, right in zip(fagan.positions, lahiri.positions, strict=True):
            assert left.lon_sidereal != right.lon_sidereal

    def test_sidereal_mode_is_rearmed_on_every_call(self, chart):
        positions.compute_positions(chart["jd_ut"], "lahiri")
        after = positions.compute_positions(chart["jd_ut"], chart["ayanamsa"]["id"])

        assert after.ayanamsa.value_deg == pytest.approx(
            chart["ayanamsa"]["value_deg"], abs=TOL["ayanamsa_deg"]
        )


class TestSupportedAyanamsas:
    @pytest.mark.parametrize("ayanamsa_id", list(bodies.AYANAMSA_IDS))
    def test_every_supported_ayanamsa_computes(self, ayanamsa_id):
        computed = positions.compute_positions(CHARTS[0]["jd_ut"], ayanamsa_id)

        assert [position.body for position in computed.positions] == list(
            bodies.ALL_BODY_IDS
        )
        assert 0 < computed.ayanamsa.value_deg < 30
