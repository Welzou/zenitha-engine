import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

FIXTURES = Path(__file__).parent / "fixtures" / "reference_charts.json"
_DATA = json.loads(FIXTURES.read_text(encoding="utf-8"))
REF01 = _DATA["charts"][0]
TOL = _DATA["_meta"]["tolerances"]


def _payload(chart: dict) -> dict:
    return {
        "date": chart["date"],
        "time": chart["time"],
        "lat": chart["lat"],
        "lng": chart["lng"],
        "ayanamsa": chart["ayanamsa"]["id"],
    }


class TestHealth:
    def test_health(self):
        response = client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["swisseph"]
        assert body["pyswisseph"]
        assert body["tzdata"]

    def test_no_key_required(self, monkeypatch):
        monkeypatch.setenv("ENGINE_API_KEY", "secret")

        response = client.get("/health")

        assert response.status_code == 200


class TestChart:
    @pytest.fixture(autouse=True)
    def _no_key_by_default(self, monkeypatch):
        monkeypatch.delenv("ENGINE_API_KEY", raising=False)

    def test_ref01_full_response(self):
        response = client.post("/v1/chart", json=_payload(REF01))

        assert response.status_code == 200
        body = response.json()

        assert body["instant"]["tz"] == REF01["tz"]
        assert body["instant"]["utc"].endswith("Z")
        assert body["instant"]["utc"] == REF01["utc"]
        assert body["instant"]["jd_ut"] == pytest.approx(REF01["jd_ut"], abs=1e-6)
        assert body["ayanamsa"]["value_deg"] == pytest.approx(
            REF01["ayanamsa"]["value_deg"], abs=TOL["ayanamsa_deg"]
        )
        assert len(body["positions"]) == 12
        assert len(body["lines"]) == 48
        assert len({line["id"] for line in body["lines"]}) == 48

    @pytest.mark.parametrize(
        ("code", "payload"),
        [
            (
                "TZ_NOT_FOUND",
                {"date": "2000-01-01", "time": "12:00", "lat": 0.0, "lng": -30.0},
            ),
            (
                "TIME_AMBIGUOUS",
                {
                    "date": "2023-10-29",
                    "time": "02:30",
                    "lat": 48.8566,
                    "lng": 2.3522,
                },
            ),
            (
                "TIME_NONEXISTENT",
                {
                    "date": "2023-03-26",
                    "time": "02:30",
                    "lat": 48.8566,
                    "lng": 2.3522,
                },
            ),
            (
                "DATE_OUT_OF_RANGE",
                {"date": "1500-01-01", "time": "12:00", "lat": 48.8566, "lng": 2.3522},
            ),
        ],
    )
    def test_error_codes(self, code, payload):
        response = client.post("/v1/chart", json=payload)

        assert response.status_code == 400
        assert response.json()["error"] == code

    def test_invalid_payload_returns_422(self):
        payload = _payload(REF01) | {"lat": 91}

        response = client.post("/v1/chart", json=payload)

        assert response.status_code == 422

    def test_missing_key_returns_401(self, monkeypatch):
        monkeypatch.setenv("ENGINE_API_KEY", "secret")

        response = client.post("/v1/chart", json=_payload(REF01))

        assert response.status_code == 401
        assert response.json()["error"] == "UNAUTHORIZED"

    def test_wrong_key_returns_401(self, monkeypatch):
        monkeypatch.setenv("ENGINE_API_KEY", "secret")

        response = client.post(
            "/v1/chart", json=_payload(REF01), headers={"X-Engine-Key": "nope"}
        )

        assert response.status_code == 401

    def test_correct_key_returns_200(self, monkeypatch):
        monkeypatch.setenv("ENGINE_API_KEY", "secret")

        response = client.post(
            "/v1/chart", json=_payload(REF01), headers={"X-Engine-Key": "secret"}
        )

        assert response.status_code == 200
