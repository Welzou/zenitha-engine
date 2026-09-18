"""Export CLI : instant + lieu → tableau des positions + 48 lignes en GeoJSON.

Enchaîne resolve_instant → compute_positions → build_lines, sans passer par
l'API HTTP. Aucune donnée de naissance en dur : tout vient des arguments.
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from app import lines, positions, schemas, timeconv

DEFAULT_LAT_STEP_DEG = 0.5


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date", required=True, type=dt.date.fromisoformat, help="YYYY-MM-DD"
    )
    parser.add_argument(
        "--time", required=True, type=dt.time.fromisoformat, help="HH:MM"
    )
    parser.add_argument("--lat", required=True, type=float)
    parser.add_argument("--lng", required=True, type=float)
    parser.add_argument(
        "--ayanamsa", default="fagan_bradley", choices=list(schemas.AyanamsaId.__args__)
    )
    parser.add_argument("--fold", type=int, choices=[0, 1], default=None)
    parser.add_argument("--lat-step-deg", type=float, default=DEFAULT_LAT_STEP_DEG)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args(argv)


def _print_positions(chart_positions: list[schemas.PositionOut]) -> None:
    for position in chart_positions:
        marker = "R" if position.retrograde else " "
        deg = f"{position.deg_in_sign:6.2f}"
        print(f"{position.body:<8} {position.sign:<12} {deg} deg {marker}")


def _feature_collection(chart_lines: list[schemas.LineOut]) -> dict[str, object]:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": line.id, "body": line.body, "angle": line.angle},
                "geometry": line.geometry.model_dump(),
            }
            for line in chart_lines
        ],
    }


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    # Les bornes viennent du schéma et non d'argparse : sans ça un pas de 0
    # divisait par zéro et un pas négatif vidait la grille de latitudes.
    try:
        request = schemas.ChartRequest(
            date=args.date,
            time=args.time,
            lat=args.lat,
            lng=args.lng,
            ayanamsa=args.ayanamsa,
            fold=args.fold,
            lat_step_deg=args.lat_step_deg,
        )
    except ValidationError as error:
        print(error, file=sys.stderr)
        return 2

    try:
        instant = timeconv.resolve_instant(
            request.date, request.time, request.lat, request.lng, request.fold
        )
    except timeconv.EngineError as error:
        print(f"{error.code}: {error.detail}", file=sys.stderr)
        return 1

    chart = positions.compute_positions(instant.jd_ut, request.ayanamsa)
    _print_positions(chart.positions)

    chart_lines = lines.build_lines(
        chart.positions, chart.gst_deg, request.lat_step_deg
    )
    args.out.write_text(json.dumps(_feature_collection(chart_lines)), encoding="utf-8")
    print(f"\n{len(chart_lines)} lignes ecrites dans {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
