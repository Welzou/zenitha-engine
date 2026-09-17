import json
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from app import bodies, schemas

FIXTURES = Path(__file__).parent / "fixtures" / "reference_charts.json"


def valid_payload(**overrides: object) -> dict[str, object]:
    payload = {
        "date": "1987-03-14",
        "time": "08:45",
        "lat": 34.0209,
        "lng": -6.8416,
    }
    payload.update(overrides)
    return payload


class TestChartRequestBounds:
    @pytest.mark.parametrize("lat", [91, -91])
    def test_lat_out_of_bounds_rejected(self, lat):
        with pytest.raises(ValidationError):
            schemas.ChartRequest(**valid_payload(lat=lat))

    @pytest.mark.parametrize("lat", [90, -90, 0])
    def test_lat_at_bounds_accepted(self, lat):
        schemas.ChartRequest(**valid_payload(lat=lat))

    @pytest.mark.parametrize("lng", [181, -181])
    def test_lng_out_of_bounds_rejected(self, lng):
        with pytest.raises(ValidationError):
            schemas.ChartRequest(**valid_payload(lng=lng))

    @pytest.mark.parametrize("step", [5, 0.05])
    def test_lat_step_deg_out_of_bounds_rejected(self, step):
        with pytest.raises(ValidationError):
            schemas.ChartRequest(**valid_payload(lat_step_deg=step))

    @pytest.mark.parametrize("step", [0.1, 2])
    def test_lat_step_deg_at_bounds_accepted(self, step):
        schemas.ChartRequest(**valid_payload(lat_step_deg=step))

    def test_unknown_ayanamsa_rejected(self):
        with pytest.raises(ValidationError):
            schemas.ChartRequest(**valid_payload(ayanamsa="invalid"))

    def test_bad_fold_rejected(self):
        with pytest.raises(ValidationError):
            schemas.ChartRequest(**valid_payload(fold=2))


class TestChartRequestDefaults:
    def test_defaults(self):
        req = schemas.ChartRequest(**valid_payload())

        assert req.ayanamsa == "fagan_bradley"
        assert req.fold is None
        assert req.lat_step_deg == 0.5


class TestLiteralsMatchBodies:
    def test_ayanamsa_id_matches_bodies_module(self):
        assert set(get_args(schemas.AyanamsaId)) == set(bodies.AYANAMSA_IDS)

    def test_body_id_matches_bodies_module(self):
        assert set(get_args(schemas.BodyId)) == set(bodies.ALL_BODY_IDS)

    def test_sign_matches_bodies_module(self):
        assert set(get_args(schemas.Sign)) == set(bodies.SIGN_IDS)


class TestChartResponseFromFixture:
    def test_all_reference_positions_validate(self):
        data = json.loads(FIXTURES.read_text(encoding="utf-8"))
        all_positions = [
            position for chart in data["charts"] for position in chart["positions"]
        ]

        assert len(all_positions) == 60
        for position in all_positions:
            schemas.PositionOut(**position)

    def test_full_response_with_fixture_instant_and_ayanamsa(self):
        data = json.loads(FIXTURES.read_text(encoding="utf-8"))
        chart = data["charts"][0]

        response = schemas.ChartResponse(
            instant={
                "tz": chart["tz"],
                "utc_offset_minutes": chart["utc_offset_minutes"],
                "utc": chart["utc"],
                "jd_ut": chart["jd_ut"],
            },
            ayanamsa=chart["ayanamsa"],
            positions=chart["positions"],
            lines=[
                {
                    "id": "sun_mc",
                    "body": "sun",
                    "angle": "mc",
                    "geometry": {
                        "type": "MultiLineString",
                        "coordinates": [[(0.0, -89.0), (0.0, 89.0)]],
                    },
                }
            ],
        )

        assert response.ayanamsa.id == chart["ayanamsa"]["id"]
        assert len(response.positions) == 12


class TestErrorResponse:
    def test_time_ambiguous_with_offsets_detail(self):
        error = schemas.ErrorResponse(
            error="TIME_AMBIGUOUS", detail={"offsets": [60, 120]}
        )

        assert error.error == "TIME_AMBIGUOUS"

    def test_unknown_error_code_rejected(self):
        with pytest.raises(ValidationError):
            schemas.ErrorResponse(error="BAD_AYANAMSA", detail="nope")
