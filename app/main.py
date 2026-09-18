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
        status_code=400, content={"error": exc.code, "detail": exc.detail}
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


@app.post("/v1/chart", response_model=schemas.ChartResponse)
def create_chart(
    payload: schemas.ChartRequest,
    x_engine_key: str | None = Header(default=None, alias="X-Engine-Key"),
) -> schemas.ChartResponse | JSONResponse:
    expected_key = os.environ.get("ENGINE_API_KEY")
    if expected_key is not None and not hmac.compare_digest(
        x_engine_key or "", expected_key
    ):
        return JSONResponse(
            status_code=401,
            content={
                "error": "UNAUTHORIZED",
                "detail": "missing or invalid X-Engine-Key",
            },
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
