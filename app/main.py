import hmac
import os
from importlib.metadata import version

import swisseph as swe
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from app import lines, positions, schemas, timeconv

app = FastAPI()


@app.exception_handler(timeconv.EngineError)
def _handle_engine_error(request: Request, exc: timeconv.EngineError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=schemas.ErrorResponse(error=exc.code, detail=exc.detail).model_dump(),
    )


@app.get("/health")
def health() -> dict[str, str]:
    # Pas de clé requise : ce endpoint sert au monitoring (systemd, uptime checks).
    return {
        "status": "ok",
        "swisseph": swe.version,
        "pyswisseph": version("pyswisseph"),
        "tzdata": version("tzdata"),
    }


@app.post(
    "/v1/chart",
    response_model=schemas.ChartResponse,
    # Sans ça l'OpenAPI n'annonce que 200 et 422 : un client généré depuis le
    # schéma ne peut pas brancher sur TIME_AMBIGUOUS pour redemander `fold`.
    responses={
        400: {"model": schemas.ErrorResponse},
        401: {"model": schemas.ErrorResponse},
    },
)
def create_chart(
    payload: schemas.ChartRequest,
    x_engine_key: str | None = Header(default=None, alias="X-Engine-Key"),
) -> schemas.ChartResponse | JSONResponse:
    # Une clé vide vaut clé absente : `EnvironmentFile` n'a pas d'autre façon
    # d'écrire « pas de clé », et une garde à moitié armée se teste faussement.
    expected_key = os.environ.get("ENGINE_API_KEY")
    if expected_key and not hmac.compare_digest(x_engine_key or "", expected_key):
        return JSONResponse(
            status_code=401,
            content=schemas.ErrorResponse(
                error="UNAUTHORIZED", detail="missing or invalid X-Engine-Key"
            ).model_dump(),
        )

    instant = timeconv.resolve_instant(
        payload.date, payload.time, payload.lat, payload.lng, payload.fold
    )
    computed = positions.compute_positions(instant.jd_ut, payload.ayanamsa)
    chart_lines = lines.build_lines(
        computed.positions, computed.gst_deg, payload.lat_step_deg
    )

    return schemas.ChartResponse(
        instant=instant,
        ayanamsa=computed.ayanamsa,
        positions=computed.positions,
        lines=chart_lines,
    )
