import json
from pathlib import Path

import pytest

from app import lines, positions, schemas

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


def meridian_longitude(geometry: schemas.LineGeometry) -> float:
    """Longitude d'un méridien, en vérifiant au passage qu'elle est constante."""
    (segment,) = geometry.coordinates
    longitudes = {lon for lon, _ in segment}

    assert len(longitudes) == 1
    return longitudes.pop()


class TestNorm180:
    @pytest.mark.parametrize(
        ("deg", "expected"),
        [
            (0.0, 0.0),
            (90.0, 90.0),
            (-90.0, -90.0),
            (180.0, 180.0),
            (-180.0, 180.0),
            (181.0, -179.0),
            (-181.0, 179.0),
            (360.0, 0.0),
            (540.0, 180.0),
            (-540.0, 180.0),
        ],
    )
    def test_maps_into_the_half_open_range(self, deg, expected):
        assert lines.norm180(deg) == expected


class TestMeridianGeometry:
    def test_spans_the_full_latitude_range(self, chart, computed):
        for position in computed.positions:
            meridians = lines.mc_ic_lines(position.ra, chart["gst_deg"])

            for geometry in (meridians.mc, meridians.ic):
                assert geometry.type == "MultiLineString"
                (segment,) = geometry.coordinates
                assert [lat for _, lat in segment] == [
                    lines.MERIDIAN_MIN_LAT,
                    lines.MERIDIAN_MAX_LAT,
                ]


class TestReferenceMeridians:
    def test_mc_and_ic_longitudes(self, chart, computed):
        for position in computed.positions:
            expected = chart["lines"][position.body]
            meridians = lines.mc_ic_lines(position.ra, chart["gst_deg"])

            assert meridian_longitude(meridians.mc) == pytest.approx(
                expected["mc_lon"], abs=TOL["line_lon_deg"]
            )
            assert meridian_longitude(meridians.ic) == pytest.approx(
                expected["ic_lon"], abs=TOL["line_lon_deg"]
            )

    def test_ic_is_opposite_mc(self, chart, computed):
        for position in computed.positions:
            meridians = lines.mc_ic_lines(position.ra, chart["gst_deg"])

            assert meridian_longitude(meridians.ic) == lines.norm180(
                meridian_longitude(meridians.mc) + 180
            )

    def test_longitudes_stay_in_range(self, chart, computed):
        for position in computed.positions:
            meridians = lines.mc_ic_lines(position.ra, chart["gst_deg"])

            for geometry in (meridians.mc, meridians.ic):
                assert -180 < meridian_longitude(geometry) <= 180
