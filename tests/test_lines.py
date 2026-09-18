import json
from pathlib import Path

import pytest
import swisseph as swe

from app import lines, positions, schemas

FIXTURES = Path(__file__).parent / "fixtures" / "reference_charts.json"
_DATA = json.loads(FIXTURES.read_text(encoding="utf-8"))
CHARTS = _DATA["charts"]
TOL = _DATA["_meta"]["tolerances"]

DEFAULT_STEP = 0.5
SYMMETRY_TOLERANCE_DEG = 1e-6
ALTITUDE_TOLERANCE_DEG = 0.1
TROMSO = CHARTS[4]


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


def longitude_by_latitude(geometry: schemas.LineGeometry) -> dict[float, float]:
    return {lat: lon for segment in geometry.coordinates for lon, lat in segment}


def body_position(chart: dict, body: str):
    computed = positions.compute_positions(chart["jd_ut"], chart["ayanamsa"]["id"])
    return next(p for p in computed.positions if p.body == body)


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
                    lines.LINE_MIN_LAT,
                    lines.LINE_MAX_LAT,
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


class TestReferenceAcDc:
    def test_longitudes_at_reference_latitudes(self, chart, computed):
        for position in computed.positions:
            expected = chart["lines"][position.body]["acdc_by_lat"]
            acdc = lines.ac_dc_lines(
                position.ra, position.dec, chart["gst_deg"], DEFAULT_STEP
            )
            ac_by_lat = longitude_by_latitude(acdc.ac)
            dc_by_lat = longitude_by_latitude(acdc.dc)

            for latitude, want in expected.items():
                lat = float(latitude)
                assert ac_by_lat[lat] == pytest.approx(
                    want["ac"], abs=TOL["line_lon_deg"]
                )
                assert dc_by_lat[lat] == pytest.approx(
                    want["dc"], abs=TOL["line_lon_deg"]
                )

    def test_ac_and_dc_are_symmetric_around_mc(self, chart, computed):
        for position in computed.positions:
            mc_lon = lines.norm180(position.ra - chart["gst_deg"])

            for lat in lines._latitudes(DEFAULT_STEP):
                found = lines._horizon_longitudes(
                    position.ra, position.dec, chart["gst_deg"], lat
                )
                if found is None:
                    continue

                ac_lon, dc_lon = found
                assert lines.norm180(mc_lon - ac_lon) == pytest.approx(
                    lines.norm180(dc_lon - mc_lon), abs=SYMMETRY_TOLERANCE_DEG
                )


class TestCircumpolar:
    # ref05, Tromsø au solstice d'été : le Soleil culmine à une déclinaison de
    # 23,44°, donc plus rien ne se lève ni ne se couche au-delà de 90 - 23,44.
    @pytest.mark.parametrize(
        ("lat", "has_solution"),
        [(60.0, True), (66.0, True), (66.5, True), (66.6, False), (70.0, False)],
    )
    def test_no_solution_beyond_the_polar_limit(self, lat, has_solution):
        sun = body_position(TROMSO, "sun")
        found = lines._horizon_longitudes(sun.ra, sun.dec, TROMSO["gst_deg"], lat)

        assert (found is not None) == has_solution

    def test_sun_never_rises_at_tromso_itself(self):
        sun = body_position(TROMSO, "sun")

        assert (
            lines._horizon_longitudes(sun.ra, sun.dec, TROMSO["gst_deg"], TROMSO["lat"])
            is None
        )

    def test_geometry_is_cut_at_the_polar_limit(self):
        sun = body_position(TROMSO, "sun")
        acdc = lines.ac_dc_lines(sun.ra, sun.dec, TROMSO["gst_deg"], DEFAULT_STEP)
        limit = 90 - abs(sun.dec)

        assert limit == pytest.approx(66.5631, abs=0.001)
        for geometry in (acdc.ac, acdc.dc):
            assert geometry.coordinates
            assert all(
                abs(lat) <= limit
                for segment in geometry.coordinates
                for _, lat in segment
            )


def curve_points(geometry: schemas.LineGeometry) -> list[tuple[float, float]]:
    return [point for segment in geometry.coordinates for point in segment]


def has_apex_in_window(dec: float) -> bool:
    return 90 - abs(dec) <= lines.LINE_MAX_LAT


class TestApex:
    def test_ac_and_dc_meet_at_the_apex(self, chart, computed):
        for position in computed.positions:
            if not has_apex_in_window(position.dec):
                continue

            acdc = lines.ac_dc_lines(
                position.ra, position.dec, chart["gst_deg"], DEFAULT_STEP
            )
            rising = curve_points(acdc.ac)
            setting = curve_points(acdc.dc)

            assert rising[0] == setting[0]
            assert rising[-1] == setting[-1]

    def test_apex_sits_at_the_polar_limit(self, chart, computed):
        for position in computed.positions:
            if not has_apex_in_window(position.dec):
                continue

            acdc = lines.ac_dc_lines(
                position.ra, position.dec, chart["gst_deg"], DEFAULT_STEP
            )
            limit = 90 - abs(position.dec)

            for geometry in (acdc.ac, acdc.dc):
                latitudes = [lat for _, lat in curve_points(geometry)]
                assert min(latitudes) == pytest.approx(-limit, abs=1e-9)
                assert max(latitudes) == pytest.approx(limit, abs=1e-9)

    # Jupiter dans ref01 et Neptune dans ref03 passent à moins d'un degré de
    # l'équateur céleste : leur latitude limite dépasse le bord de la carte,
    # donc leur courbe sort par le haut sans se refermer.
    @pytest.mark.parametrize(("chart_index", "body"), [(0, "jupiter"), (2, "neptune")])
    def test_curve_stays_open_without_an_apex(self, chart_index, body):
        chart = CHARTS[chart_index]
        position = body_position(chart, body)
        acdc = lines.ac_dc_lines(
            position.ra, position.dec, chart["gst_deg"], DEFAULT_STEP
        )

        assert not has_apex_in_window(position.dec)
        latitudes = [lat for _, lat in curve_points(acdc.ac)]
        assert min(latitudes) == lines.LINE_MIN_LAT
        assert max(latitudes) == lines.LINE_MAX_LAT


class TestDensification:
    def test_no_longitude_gap_above_the_threshold(self, chart, computed):
        for position in computed.positions:
            acdc = lines.ac_dc_lines(
                position.ra, position.dec, chart["gst_deg"], DEFAULT_STEP
            )

            for geometry in (acdc.ac, acdc.dc):
                for segment in geometry.coordinates:
                    for (left, _), (right, _) in zip(segment, segment[1:]):
                        assert abs(right - left) <= lines._MAX_LONGITUDE_GAP_DEG

    def test_densification_only_adds_latitudes(self, chart, computed):
        for position in computed.positions:
            produced = {
                lat for lat, _ in lines._horizon_samples(position.dec, DEFAULT_STEP)
            }
            from_grid = {
                lat
                for lat in lines._latitudes(DEFAULT_STEP)
                if lines._hour_angle(position.dec, lat) is not None
            }

            assert from_grid <= produced


class TestAntimeridianInterpolation:
    # Les deux corps dont l'apex tombe sur l'antiméridien : Pluton (MC à
    # -179,91°) et Mercure (IC à -179,63°). Sans les points de traversée leur
    # apex restait seul dans son segment, était filtré, et la courbe finissait
    # ouverte d'un côté.
    @pytest.mark.parametrize(("chart_index", "body"), [(4, "pluto"), (1, "mercury")])
    def test_crossing_inserts_both_map_edges(self, chart_index, body):
        chart = CHARTS[chart_index]
        position = body_position(chart, body)
        acdc = lines.ac_dc_lines(
            position.ra, position.dec, chart["gst_deg"], DEFAULT_STEP
        )

        crossings = 0
        for geometry in (acdc.ac, acdc.dc):
            for leaving, entering in zip(
                geometry.coordinates, geometry.coordinates[1:]
            ):
                exit_lon, exit_lat = leaving[-1]
                entry_lon, entry_lat = entering[0]

                assert abs(exit_lon) == 180.0
                assert entry_lon == -exit_lon
                assert exit_lat == entry_lat
                crossings += 1

        assert crossings

    def test_the_single_point_filter_never_fires(self, chart, computed):
        for position in computed.positions:
            samples = lines._horizon_samples(position.dec, DEFAULT_STEP)

            for index in (0, 1):
                points = [
                    (
                        lines._longitudes(position.ra, chart["gst_deg"], hour_angle)[
                            index
                        ],
                        lat,
                    )
                    for lat, hour_angle in samples
                ]
                raw = lines._split_segments(points)

                assert sum(len(segment) for segment in raw) == sum(
                    len(segment) for segment in raw if len(segment) >= 2
                )


class TestHorizonAltitude:
    def test_ac_and_dc_points_are_on_the_horizon(self, chart, computed):
        # Seul test du moteur qui ne rejoue pas nos formules : il redemande à
        # swisseph ce que l'on voit du Soleil depuis un point de chaque courbe.
        sun = next(p for p in computed.positions if p.body == "sun")
        acdc = lines.ac_dc_lines(sun.ra, sun.dec, chart["gst_deg"], DEFAULT_STEP)

        for geometry, rising in ((acdc.ac, True), (acdc.dc, False)):
            lon = longitude_by_latitude(geometry)[30.0]
            azimuth, true_altitude, _ = swe.azalt(
                chart["jd_ut"],
                swe.EQU2HOR,
                (lon, 30.0, 0.0),
                0.0,
                0.0,
                (sun.ra, sun.dec, 1.0),
            )

            assert true_altitude == pytest.approx(
                chart["check_sun_ac_altitude_deg_at_lat30"],
                abs=ALTITUDE_TOLERANCE_DEG,
            )
            # Azimut swisseph : 0 = sud, 90 = ouest, 180 = nord, 270 = est.
            # L'altitude seule ne sépare pas lever et coucher — les deux valent
            # zéro. L'azimut le fait : on se lève à l'est, on se couche à l'ouest.
            assert (azimuth > 180) == rising


class TestMultiline:
    # Les deux règles de découpe, testées directement : sur une courbe réelle la
    # zone circumpolaire tombe toujours aux deux extrémités du balayage, donc un
    # `None` n'y coupe jamais rien au milieu et aucun test d'intégration ne
    # pourrait distinguer la coupure d'une simple concaténation.
    def test_a_gap_splits_the_line(self):
        points = [(0.0, -2.0), (1.0, -1.0), None, (2.0, 1.0), (3.0, 2.0)]

        assert len(lines._multiline(points).coordinates) == 2

    def test_an_antimeridian_crossing_splits_the_line(self):
        points = [(179.0, -1.0), (179.5, -0.5), (-179.5, 0.0), (-179.0, 0.5)]

        assert len(lines._multiline(points).coordinates) == 2

    def test_single_point_segments_are_dropped(self):
        points = [(0.0, -2.0), None, (50.0, 0.0), None, (2.0, 1.0), (3.0, 2.0)]

        assert lines._multiline(points).coordinates == [[(2.0, 1.0), (3.0, 2.0)]]


class TestSegmentation:
    def test_segments_never_jump_the_antimeridian(self, chart, computed):
        for position in computed.positions:
            acdc = lines.ac_dc_lines(
                position.ra, position.dec, chart["gst_deg"], DEFAULT_STEP
            )

            for geometry in (acdc.ac, acdc.dc):
                for segment in geometry.coordinates:
                    for (left, _), (right, _) in zip(segment, segment[1:]):
                        assert abs(right - left) <= 180

    def test_every_segment_is_a_valid_linestring(self, chart, computed):
        for position in computed.positions:
            acdc = lines.ac_dc_lines(
                position.ra, position.dec, chart["gst_deg"], DEFAULT_STEP
            )

            for geometry in (acdc.ac, acdc.dc):
                assert geometry.coordinates
                for segment in geometry.coordinates:
                    assert len(segment) >= 2

    def test_latitudes_increase_within_each_segment(self, chart, computed):
        for position in computed.positions:
            acdc = lines.ac_dc_lines(
                position.ra, position.dec, chart["gst_deg"], DEFAULT_STEP
            )

            for geometry in (acdc.ac, acdc.dc):
                for segment in geometry.coordinates:
                    latitudes = [lat for _, lat in segment]
                    assert latitudes == sorted(latitudes)
                    assert lines.LINE_MIN_LAT <= latitudes[0]
                    assert latitudes[-1] <= lines.LINE_MAX_LAT


class TestSamplingStep:
    def test_step_controls_sampling_density(self):
        sun = body_position(CHARTS[0], "sun")
        gst = CHARTS[0]["gst_deg"]

        def point_count(step: float) -> int:
            acdc = lines.ac_dc_lines(sun.ra, sun.dec, gst, step)
            return sum(len(segment) for segment in acdc.ac.coordinates)

        assert point_count(2.0) < point_count(0.5) < point_count(0.1)
