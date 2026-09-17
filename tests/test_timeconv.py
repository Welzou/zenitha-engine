import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app import timeconv

FIXTURES = Path(__file__).parent / "fixtures" / "reference_charts.json"
CHARTS = json.loads(FIXTURES.read_text(encoding="utf-8"))["charts"]

# Les jd_ut des fixtures sont arrondis à 6 décimales (0,086 s) ; _meta.tolerances
# n'en fixe pas, la spec demande l'instant UT « exact à la seconde » (1,2e-5 jd).
JD_TOLERANCE = 1e-6

PARIS_LAT, PARIS_LNG = 48.8566, 2.3522


def chart_args(chart: dict) -> dict:
    return {
        "date": dt.date.fromisoformat(chart["date"]),
        "time": dt.time.fromisoformat(chart["time"]),
        "lat": chart["lat"],
        "lng": chart["lng"],
    }


@pytest.fixture(params=CHARTS, ids=[chart["id"] for chart in CHARTS])
def chart(request):
    return request.param


class TestReferenceCharts:
    def test_resolves_tz_offset_and_instant(self, chart):
        instant = timeconv.resolve_instant(**chart_args(chart))

        assert instant.tz == chart["tz"]
        assert instant.utc_offset_minutes == chart["utc_offset_minutes"]
        assert instant.utc == dt.datetime.fromisoformat(chart["utc"])
        assert instant.jd_ut == pytest.approx(chart["jd_ut"], abs=JD_TOLERANCE)

    def test_utc_roundtrips_to_the_local_wall_clock(self, chart):
        instant = timeconv.resolve_instant(**chart_args(chart))

        local = instant.utc.astimezone(ZoneInfo(instant.tz))

        assert local.replace(tzinfo=None) == dt.datetime.combine(
            dt.date.fromisoformat(chart["date"]),
            dt.time.fromisoformat(chart["time"]),
        )


class TestAmbiguousTime:
    # Paris 2023-10-29 : les horloges reculent de 03:00 CEST à 02:00 CET,
    # 02:30 est donc vécu deux fois.
    ARGS: dict = {
        "date": dt.date(2023, 10, 29),
        "time": dt.time(2, 30),
        "lat": PARIS_LAT,
        "lng": PARIS_LNG,
    }

    def test_raises_with_both_offsets_when_fold_is_missing(self):
        with pytest.raises(timeconv.TimeAmbiguous) as excinfo:
            timeconv.resolve_instant(**self.ARGS)

        assert excinfo.value.code == "TIME_AMBIGUOUS"
        assert excinfo.value.detail == {"offsets": [120, 60]}

    def test_fold_0_picks_the_first_occurrence(self):
        instant = timeconv.resolve_instant(**self.ARGS, fold=0)

        assert instant.utc_offset_minutes == 120
        assert instant.utc == dt.datetime(2023, 10, 29, 0, 30, tzinfo=dt.timezone.utc)

    def test_fold_1_picks_the_second_occurrence(self):
        instant = timeconv.resolve_instant(**self.ARGS, fold=1)

        assert instant.utc_offset_minutes == 60
        assert instant.utc == dt.datetime(2023, 10, 29, 1, 30, tzinfo=dt.timezone.utc)


class TestNonexistentTime:
    # Paris 2023-03-26 : les horloges sautent de 02:00 CET à 03:00 CEST,
    # 02:30 n'existe pas.
    ARGS: dict = {
        "date": dt.date(2023, 3, 26),
        "time": dt.time(2, 30),
        "lat": PARIS_LAT,
        "lng": PARIS_LNG,
    }

    @pytest.mark.parametrize("fold", [None, 0, 1])
    def test_raises_whatever_the_fold(self, fold):
        with pytest.raises(timeconv.TimeNonexistent) as excinfo:
            timeconv.resolve_instant(**self.ARGS, fold=fold)

        assert excinfo.value.code == "TIME_NONEXISTENT"


class TestFoldOutsideATransition:
    def test_fold_changes_nothing_on_an_ordinary_time(self):
        args = chart_args(CHARTS[0])
        baseline = timeconv.resolve_instant(**args)

        assert timeconv.resolve_instant(**args, fold=0) == baseline
        assert timeconv.resolve_instant(**args, fold=1) == baseline


class TestTimezoneNotFound:
    def test_open_sea_has_no_timezone(self):
        # timezone_at() renverrait le fuseau nautique Etc/GMT+10 ici : seul
        # timezone_at_land() distingue la pleine mer.
        with pytest.raises(timeconv.TzNotFound) as excinfo:
            timeconv.resolve_instant(
                date=dt.date(1987, 3, 14),
                time=dt.time(8, 45),
                lat=0.0,
                lng=-150.0,
            )

        assert excinfo.value.code == "TZ_NOT_FOUND"


class TestDateRange:
    @pytest.mark.parametrize("birth_date", [dt.date(1799, 12, 31), dt.date(2200, 1, 1)])
    def test_outside_the_supported_range_rejected(self, birth_date):
        with pytest.raises(timeconv.DateOutOfRange) as excinfo:
            timeconv.resolve_instant(
                date=birth_date,
                time=dt.time(12, 0),
                lat=PARIS_LAT,
                lng=PARIS_LNG,
            )

        assert excinfo.value.code == "DATE_OUT_OF_RANGE"
        assert excinfo.value.detail == {"min": "1800-01-01", "max": "2199-12-31"}

    @pytest.mark.parametrize("birth_date", [dt.date(1800, 1, 1), dt.date(2199, 12, 31)])
    def test_bounds_are_accepted(self, birth_date):
        instant = timeconv.resolve_instant(
            date=birth_date,
            time=dt.time(12, 0),
            lat=PARIS_LAT,
            lng=PARIS_LNG,
        )

        assert instant.tz == "Europe/Paris"
