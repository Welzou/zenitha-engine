from importlib.metadata import version

import swisseph as swe
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "swisseph": swe.version,
        "pyswisseph": version("pyswisseph"),
        "tzdata": version("tzdata"),
    }
